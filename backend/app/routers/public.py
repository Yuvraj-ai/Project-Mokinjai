"""The public /v1 surface (plan Task 3): `POST /v1/chat`, `GET /v1/agent`.

The key's workspace is the boundary; the agent is named per request. History
is server-side: with a `conversation_id` the turn appends to that session
(the key may only use sessions it created); without one, every call creates
a fresh session — so `stream_turn` is reused unchanged, one chat path for
the Playground and the public API alike.

Errors are raised, not returned: the sub-application's exception handlers
(main.py) convert them into the public `{error: {...}}` envelope.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.public_auth import PublicAuthError, get_api_key
from app.models.agent import Agent
from app.models.api_key import ApiKey
from app.models.chat import ChatMessage, ChatSession
from app.models.execution import Execution
from app.services.agent_composition import CompositionError, saved_input, validate_agent
from app.services.agent_runtime import stream_turn
from app.utils.errors import NotFoundException

router = APIRouter()


class PublicChatRequest(BaseModel):
    agent_id: str | None = Field(default=None, description="Required without conversation_id.")
    message: str = Field(min_length=1, max_length=32_000)
    conversation_id: str | None = None
    stream: bool = False


class PublicAgentEntry(BaseModel):
    id: str
    name: str
    description: str | None
    status: str


def _sse(events):
    async def generate():
        async for event in events:
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

    return generate()


async def _resolve_conversation(
    db: AsyncSession, key: ApiKey, body: PublicChatRequest
) -> ChatSession:
    """The session this turn belongs to.

    Without conversation_id a fresh session is created (stamped with the key),
    so the runtime is reused unchanged. With one, the session must belong to
    this key — a foreign id is a 404, never a history leak."""
    if body.conversation_id:
        session = (
            await db.execute(
                select(ChatSession).where(
                    ChatSession.id == body.conversation_id,
                    ChatSession.api_key_id == key.id,
                )
            )
        ).scalar_one_or_none()
        if session is None:
            # Foreign or unknown: the same 404 either way — it must not reveal
            # whether the id exists for someone else.
            raise PublicAuthError(
                "conversation_not_found", "No such conversation for this key."
            )
        if body.agent_id and body.agent_id != session.agent_id:
            raise PublicAuthError(
                "agent_mismatch", "This conversation is with a different agent."
            )
        return session

    if not body.agent_id:
        raise PublicAuthError(
            "invalid_request", "agent_id is required without conversation_id."
        )
    agent = (
        await db.execute(
            select(Agent).where(
                Agent.id == body.agent_id, Agent.workspace_id == key.workspace_id
            )
        )
    ).scalar_one_or_none()
    if agent is None:
        raise NotFoundException("Agent")
    session = ChatSession(
        workspace_id=key.workspace_id,
        agent_id=agent.id,
        api_key_id=key.id,
        title=body.message.split("\n", 1)[0].strip()[:60] or "New session",
    )
    db.add(session)
    await db.flush()
    return session


async def _load_agent(db: AsyncSession, key: ApiKey, session: ChatSession) -> Agent:
    agent = (
        await db.execute(
            select(Agent).where(
                Agent.id == session.agent_id, Agent.workspace_id == key.workspace_id
            )
        )
    ).scalar_one_or_none()
    if agent is None:
        raise NotFoundException("Agent")
    # Readiness is composition, not a column: an agent the runtime cannot
    # build is 403 before any Execution row or model call exists.
    try:
        await validate_agent(db, key.workspace_id, await saved_input(db, agent), agent_id=agent.id)
    except CompositionError as exc:
        first = exc.errors[0] if exc.errors else None
        raise PublicAuthError(
            "agent_unavailable",
            f"This agent needs attention before it can run"
            + (f": {first.field}: {first.message}" if first else "."),
        )
    return agent


@router.post("/chat")
async def public_chat(
    body: PublicChatRequest,
    request: Request,
    key: ApiKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    session = await _resolve_conversation(db, key, body)
    agent = await _load_agent(db, key, session)

    execution = Execution(
        workspace_id=key.workspace_id,
        agent_id=session.agent_id,
        api_key_id=key.id,
        status="running",
        trigger_type="api",
        input_data={"content": body.message, "conversation_id": session.id},
        started_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    if body.stream:
        return StreamingResponse(
            _sse(stream_turn(key.workspace_id, session.id, body.message, execution.id)),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Buffered: fold the stream into one response.
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    activity: list[dict] = []
    usage: dict = {}
    cost = 0.0
    status = "completed"
    error_detail: str | None = None
    async for event in stream_turn(key.workspace_id, session.id, body.message, execution.id):
        kind = event["event"]
        if kind == "token":
            content_parts.append(event["data"]["delta"])
        elif kind == "reasoning":
            reasoning_parts.append(event["data"]["delta"])
        elif kind == "activity":
            activity.append(event["data"])
        elif kind == "done":
            usage = event["data"].get("usage", {})
            cost = event["data"].get("cost_usd", 0.0)
            status = event["data"].get("status", "completed")
        elif kind == "error":
            error_detail = event["data"]["detail"]
            status = "failed"

    assistant = (
        await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id, ChatMessage.role == "assistant")
            .order_by(ChatMessage.seq.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return {
        "conversation_id": session.id,
        "message_id": assistant.id if assistant else None,
        "agent_id": session.agent_id,
        "content": "".join(content_parts),
        "reasoning": "".join(reasoning_parts) or None,
        "activity": activity,
        "status": status,
        "error": error_detail,
        "usage": usage,
        "cost_usd": cost,
        "execution_id": execution.id,
    }


@router.get("/agent")
async def list_callable_agents(
    key: ApiKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """The key's callable agents — enough to build a picker, no prompts."""
    agents = (
        (
            await db.execute(
                select(Agent)
                .where(Agent.workspace_id == key.workspace_id)
                .order_by(Agent.name)
            )
        )
        .scalars()
        .all()
    )
    entries = []
    for agent in agents:
        try:
            await validate_agent(
                db, key.workspace_id, await saved_input(db, agent), agent_id=agent.id
            )
            status = "ready"
        except CompositionError:
            status = "needs_attention"
        entries.append(
            PublicAgentEntry(
                id=agent.id, name=agent.name, description=agent.description, status=status
            )
        )
    return {"agents": [entry.model_dump() for entry in entries]}


@router.get("/health")
async def public_health():
    return {"status": "ok"}
