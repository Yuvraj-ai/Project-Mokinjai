"""Playground chat sessions (spec §5, plan Task 2).

A session is a server-owned thread for one agent. The client never sends
history — `POST .../sessions/{id}/chat` (Task 4) takes only the new message.
Reads are viewer, writes are editor; a session in another workspace is a 404,
never a 403 leak.
"""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import logger
from app.middleware.rbac import require_workspace_role
from app.models.agent import Agent
from app.models.chat import ChatMessage, ChatSession
from app.models.execution import Execution
from app.models.workspace import WorkspaceMember
from app.schemas.playground import (
    ChatSessionCreate,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatSessionResponse,
    ChatSessionUpdate,
    ChatMessageResponse,
    PlaygroundChatRequest,
)
from app.services.agent_runtime import stream_turn
from app.utils.errors import BadRequestException, NotFoundException

router = APIRouter()

_SESSION_LIST_CAP = 200

# Idle SSE streams emit a comment ping at this cadence. The ping is load
# bearing twice over: uvicorn only notices a gone client when a write fails,
# so a hung turn (unreachable MCP server, stuck tool) with nothing to say
# used to sit "running" forever, and proxies quietly buffer quiet streams.
_SSE_PING_SECONDS = 15.0


def _sse(events):
    """SSE frames from the runtime's event dicts, with idle pings.

    A pump task iterates the runtime generator into a queue so the frame loop
    can wait with a timeout; closing the frame generator cancels the pump,
    whose cancellation propagates into the runtime generator's own cleanup
    (finalizing the assistant message as stopped)."""
    async def generate():
        queue: asyncio.Queue = asyncio.Queue()

        async def pump():
            try:
                async for event in events:
                    await queue.put(event)
            except BaseException as exc:
                await queue.put(exc)
            else:
                await queue.put(None)

        task = asyncio.create_task(pump())
        try:
            while True:
                try:
                    item = await asyncio.wait_for(
                        queue.get(), timeout=_SSE_PING_SECONDS
                    )
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                if item is None:
                    break
                if isinstance(item, BaseException):
                    raise item
                yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
        finally:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    return generate()


@router.post("/sessions/{session_id}/chat")
async def chat_in_session(
    workspace_id: str,
    session_id: str,
    request: PlaygroundChatRequest,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """One playground turn. The client sends only the new message — history is
    server-owned. Each turn records one Execution (trigger_type=chat)."""
    chat_session = await _load_session(db, workspace_id, session_id)
    execution = Execution(
        workspace_id=workspace_id,
        agent_id=chat_session.agent_id,
        status="running",
        trigger_type="chat",
        input_data={"content": request.content},
        started_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    return StreamingResponse(
        _sse(
            stream_turn(
                workspace_id, chat_session.id, request.content, execution.id
            )
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
