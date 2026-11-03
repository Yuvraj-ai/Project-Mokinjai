"""Model-level behaviour of the playground chat tables (plan Task 1).

Schema and cascade rules only — HTTP behaviour lives in test_playground_sessions.py
and turn behaviour in test_playground_chat.py.
"""

import pytest
from sqlalchemy import select

from app.models.agent import Agent
from app.models.chat import ChatMessage, ChatSession


@pytest.mark.asyncio
async def test_agent_delete_cascades_sessions_and_messages(
    db_session, test_workspace, test_user
):
    agent = Agent(
        workspace_id=test_workspace.id,
        name="A",
        llm_profile_id=None,
        system_prompt="",
        params={},
    )
    db_session.add(agent)
    await db_session.flush()

    session = ChatSession(
        workspace_id=test_workspace.id,
        agent_id=agent.id,
        title="New session",
        created_by=test_user.id,
    )
    db_session.add(session)
    await db_session.flush()
    session_id = session.id
    db_session.add(ChatMessage(session_id=session_id, role="user", content="hi"))
    await db_session.commit()

    await db_session.delete(agent)
    await db_session.commit()

    remaining = (
        await db_session.execute(select(ChatSession).where(ChatSession.id == session_id))
    ).scalars().all()
    assert remaining == []
    assert (await db_session.execute(select(ChatMessage))).scalars().all() == []


@pytest.mark.asyncio
async def test_message_defaults_and_assistant_fields(db_session, test_workspace):
    agent = Agent(
        workspace_id=test_workspace.id,
        name="B",
        llm_profile_id=None,
        system_prompt="",
        params={},
    )
    db_session.add(agent)
    await db_session.flush()

    session = ChatSession(workspace_id=test_workspace.id, agent_id=agent.id)
    db_session.add(session)
    await db_session.flush()

    empty = ChatMessage(session_id=session.id, role="user")
    full = ChatMessage(
        session_id=session.id,
        role="assistant",
        content="Hello",
        reasoning="thinking...",
        activity=[{"type": "tool_start", "name": "query_data_source"}],
        structured={"answer": 42},
        status="completed",
        usage={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
        cost_usd="0.000034",
        execution_id=None,
    )
    db_session.add_all([empty, full])
    await db_session.commit()

    await db_session.refresh(empty)
    await db_session.refresh(full)
    await db_session.refresh(session)

    assert empty.content == ""
    assert empty.reasoning is None and empty.activity is None
    assert session.title is not None  # server/text default if any; router sets "New session"
    assert full.activity[0]["name"] == "query_data_source"
    assert full.usage["total_tokens"] == 3
    assert float(full.cost_usd) == 0.000034
