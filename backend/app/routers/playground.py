"""Playground chat sessions (spec §5, plan Task 2).

A session is a server-owned thread for one agent. The client never sends
history — `POST .../sessions/{id}/chat` (Task 4) takes only the new message.
Reads are viewer, writes are editor; a session in another workspace is a 404,
never a 403 leak.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import logger
from app.middleware.rbac import require_workspace_role
from app.models.agent import Agent
from app.models.chat import ChatMessage, ChatSession
from app.models.workspace import WorkspaceMember
from app.schemas.playground import (
    ChatSessionCreate,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatSessionUpdate,
    ChatMessageResponse,
)
from app.utils.errors import BadRequestException, NotFoundException

router = APIRouter()

_SESSION_LIST_CAP = 200


def _to_response(row: ChatSession) -> ChatSessionResponse:
    return ChatSessionResponse(
        id=row.id,
        workspace_id=row.workspace_id,
        agent_id=row.agent_id,
        title=row.title,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_message_response(row: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=row.id,
        session_id=row.session_id,
        role=row.role,
        content=row.content,
        reasoning=row.reasoning,
        activity=row.activity,
        structured=row.structured,
        status=row.status,
        usage=row.usage,
        cost_usd=float(row.cost_usd) if row.cost_usd is not None else None,
        execution_id=row.execution_id,
        created_at=row.created_at,
    )


async def _load_session(
    db: AsyncSession, workspace_id: str, session_id: str
) -> ChatSession:
    row = (
        await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundException("Chat session")
    return row


async def _load_agent(db: AsyncSession, workspace_id: str, agent_id: str) -> Agent:
    agent = (
        await db.execute(
            select(Agent).where(
                Agent.id == agent_id, Agent.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if agent is None:
        raise NotFoundException("Agent")
    return agent


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    workspace_id: str,
    agent_id: str | None = None,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    filters = [ChatSession.workspace_id == workspace_id]
    if agent_id is not None:
        filters.append(ChatSession.agent_id == agent_id)
    total = (
        await db.execute(
            select(func.count()).select_from(ChatSession).where(*filters)
        )
    ).scalar_one()
    rows = (
        (
            await db.execute(
                select(ChatSession)
                .where(*filters)
                .order_by(ChatSession.updated_at.desc())
                .limit(_SESSION_LIST_CAP)
            )
        )
        .scalars()
        .all()
    )
    return ChatSessionListResponse(
        sessions=[_to_response(row) for row in rows], total=total
    )


@router.post("/sessions", response_model=ChatSessionResponse, status_code=201)
async def create_session(
    workspace_id: str,
    request: ChatSessionCreate,
    member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    await _load_agent(db, workspace_id, request.agent_id)
    row = ChatSession(
        workspace_id=workspace_id,
        agent_id=request.agent_id,
        title="New session",
        created_by=member.user_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info(f"Playground session {row.id} created for agent {row.agent_id}")
    return _to_response(row)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
async def get_session(
    workspace_id: str,
    session_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    row = await _load_session(db, workspace_id, session_id)
    messages = (
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.seq)
            )
        )
        .scalars()
        .all()
    )
    detail = ChatSessionDetailResponse(
        **_to_response(row).model_dump(),
        messages=[_to_message_response(message) for message in messages],
    )
    return detail


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def rename_session(
    workspace_id: str,
    session_id: str,
    request: ChatSessionUpdate,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    row = await _load_session(db, workspace_id, session_id)
    if request.title is not None:
        title = request.title.strip()
        if not title:
            raise BadRequestException("The session title cannot be empty")
        row.title = title[:255]
    await db.commit()
    await db.refresh(row)
    return _to_response(row)


@router.delete("/sessions/{session_id}")
async def delete_session(
    workspace_id: str,
    session_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    row = await _load_session(db, workspace_id, session_id)
    await db.delete(row)
    await db.commit()
    logger.info(f"Playground session {session_id} deleted")
    return {"success": True}
