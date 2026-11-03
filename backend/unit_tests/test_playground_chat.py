"""stream_turn runtime behaviour (plan Task 3): v2 events, caps, persistence.

Runtime-level, mirroring test_agent_runtime.py::TestChatStream — monkeypatch
`async_session` and `build_graph`, then assert on the event sequence and the
persisted chat_messages rows.
"""

import asyncio
import json

import pytest
from cryptography.fernet import Fernet
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from sqlalchemy import select

from app.config import get_settings
from app.crypto import encrypt_api_key
from app.models.agent import Agent
from app.models.chat import ChatMessage, ChatSession
from app.models.execution import Execution
from app.models.llm_profile import LlmProfile
from app.services.agent_runtime import _tool_kind, stream_turn


@pytest.fixture
def encryption_key():
    settings = get_settings()
    previous = getattr(settings, "LLM_ENCRYPTION_KEY", "")
    settings.LLM_ENCRYPTION_KEY = Fernet.generate_key().decode()
    yield settings.LLM_ENCRYPTION_KEY
    settings.LLM_ENCRYPTION_KEY = previous


def make_profile(workspace_id: str) -> LlmProfile:
    return LlmProfile(
        workspace_id=workspace_id,
        name="Primary",
        provider="openai",
        model_id="gpt-4o-mini",
        encrypted_api_key=encrypt_api_key("sk-test"),
        context_window=128000,
        compaction_at_tokens=102400,
        input_price_per_million=2.0,
        output_price_per_million=10.0,
        cache_price_per_million=0.5,
        status="verified",
    )


class FakeGraphV2:
    """Reasoning delta, one tool round-trip, then streamed text."""

    def __init__(self):
        self.payloads: list[dict] = []

    async def astream_events(self, payload, version):
        self.payloads.append(payload)
        yield {
            "event": "on_chat_model_stream",
            "metadata": {"langgraph_checkpoint_ns": "model:1"},
            "data": {
                "chunk": AIMessageChunk(
                    content="", additional_kwargs={"reasoning_content": "thinking hard"}
                )
            },
        }
        yield {
            "event": "on_tool_start",
            "run_id": "run-1",
            "name": "query_data_source",
            "metadata": {},
            "data": {"input": {"connection_id": "c1", "sql": "SELECT 1"}},
        }
        yield {
            "event": "on_tool_end",
            "run_id": "run-1",
            "name": "query_data_source",
            "metadata": {},
            "data": {"output": "2 rows"},
        }
        yield {
            "event": "on_chat_model_stream",
            "metadata": {"langgraph_checkpoint_ns": "model:1"},
            "data": {"chunk": AIMessageChunk(content="Hel")},
        }
        yield {
            "event": "on_chat_model_stream",
            "metadata": {"langgraph_checkpoint_ns": "model:1"},
            "data": {"chunk": AIMessageChunk(content="lo")},
        }
        yield {
            "event": "on_chat_model_end",
            "metadata": {},
            "data": {
                "output": AIMessage(
                    content="Hello",
                    usage_metadata={
                        "input_tokens": 10,
                        "output_tokens": 2,
                        "total_tokens": 12,
                        "input_token_details": {"cache_read": 4},
                    },
                )
            },
        }
        yield {
            "event": "on_chain_end",
            "name": "LangGraph",
            "parent_ids": [],
            "metadata": {},
            "data": {"output": {"messages": [AIMessage(content="Hello")]}},
        }


async def _setup(db_session, test_workspace):
    profile = make_profile(test_workspace.id)
    db_session.add(profile)
    await db_session.flush()
    agent = Agent(
        workspace_id=test_workspace.id,
        name="Chatty",
        llm_profile_id=profile.id,
        system_prompt="Be brief.",
        params={},
    )
    db_session.add(agent)
    await db_session.flush()
    chat_session = ChatSession(workspace_id=test_workspace.id, agent_id=agent.id)
    db_session.add(chat_session)
    await db_session.flush()
    execution = Execution(
        workspace_id=test_workspace.id,
        agent_id=agent.id,
        status="running",
        trigger_type="chat",
        input_data={},
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(agent)
    await db_session.refresh(chat_session)
    await db_session.refresh(execution)
    return agent, chat_session, execution


def _install(monkeypatch, session_factory, graph):
    monkeypatch.setattr("app.services.agent_runtime.async_session", session_factory)
    monkeypatch.setattr(
        "app.services.agent_runtime.build_graph", lambda *a, **k: graph
    )


class TestStreamTurn:
    @pytest.mark.asyncio
    async def test_turn_persists_messages_and_emits_v2_events(
        self, db_session, session_factory, test_workspace, monkeypatch, encryption_key
    ):
        agent, chat_session, execution = await _setup(db_session, test_workspace)
        graph = FakeGraphV2()
        _install(monkeypatch, session_factory, graph)

        events = [
            event
            async for event in stream_turn(
                test_workspace.id, chat_session.id, "hi", execution.id
            )
        ]

        kinds = [event["event"] for event in events]
        assert kinds[0] == "message"
        assert set(kinds[0:2] + kinds[2:]) >= {"message", "reasoning", "activity", "token", "done"}
        assert kinds[-1] == "done"

        message_event = events[0]["data"]
        assert message_event["assistant_message_id"] != message_event["user_message_id"]

        reasoning = [e for e in events if e["event"] == "reasoning"]
        assert reasoning[0]["data"]["delta"] == "thinking hard"

        activities = [e["data"] for e in events if e["event"] == "activity"]
        assert activities[0]["type"] == "tool_start"
        assert activities[0]["kind"] == "sql"
        assert activities[0]["args"]["sql"] == "SELECT 1"
        assert activities[1]["type"] == "tool_end"
        assert activities[1]["result"] == "2 rows"
        assert activities[1]["id"] == activities[0]["id"]

        tokens = [e["data"]["delta"] for e in events if e["event"] == "token"]
        assert tokens == ["Hel", "lo"]

        done = events[-1]["data"]
        assert done["status"] == "completed"
        assert done["usage"]["input_tokens"] == 10
        assert done["cost_usd"] == pytest.approx(0.000034)

        async with session_factory() as check:
            rows = (
                (
                    await check.execute(
                        select(ChatMessage)
                        .where(ChatMessage.session_id == chat_session.id)
                        .order_by(ChatMessage.seq)
                    )
                )
                .scalars()
                .all()
            )
            assert [row.role for row in rows] == ["user", "assistant"]
            assert rows[0].content == "hi"
            assert rows[1].content == "Hello"
            assert rows[1].reasoning == "thinking hard"
            assert rows[1].status == "completed"
            assert rows[1].activity is not None and len(rows[1].activity) == 2
            assert rows[1].usage["total_tokens"] == 12
            assert rows[1].execution_id == execution.id
            session_row = await check.get(ChatSession, chat_session.id)
            assert session_row.title == "hi"

    def test_tool_kind_mapping(self):
        assert _tool_kind("query_data_source") == "sql"
        assert _tool_kind("describe_data_source") == "sql"
        assert _tool_kind("execute_python") == "code"
        assert _tool_kind("read_skill") == "skill"
        assert _tool_kind("tavily_search") == "web"
        assert _tool_kind("exa_search_results") == "web"
        assert _tool_kind("ask_helper_ab12") == "subagent"
        assert _tool_kind("github_create_issue") == "tool"
        assert _tool_kind("my_custom_tool") == "tool"

    @pytest.mark.asyncio
    async def test_persisted_activity_matches_streamed_events(
        self, db_session, session_factory, test_workspace, monkeypatch, encryption_key
    ):
        agent, chat_session, execution = await _setup(db_session, test_workspace)
        graph = FakeGraphV2()
        _install(monkeypatch, session_factory, graph)

        events = [
            event
            async for event in stream_turn(
                test_workspace.id, chat_session.id, "hi", execution.id
            )
        ]
        streamed = [e["data"] for e in events if e["event"] == "activity"]

        async with session_factory() as check:
            row = (
                (
                    await check.execute(
                        select(ChatMessage).where(
                            ChatMessage.session_id == chat_session.id,
                            ChatMessage.role == "assistant",
                        )
                    )
                )
                .scalars()
                .one()
            )
            assert json.loads(json.dumps(row.activity)) == streamed

    @pytest.mark.asyncio
    async def test_second_turn_loads_persisted_history(
        self, db_session, session_factory, test_workspace, monkeypatch, encryption_key
    ):
        agent, chat_session, execution = await _setup(db_session, test_workspace)
        graph = FakeGraphV2()
        _install(monkeypatch, session_factory, graph)

        async for _ in stream_turn(
            test_workspace.id, chat_session.id, "hi", execution.id
        ):
            pass

        async for _ in stream_turn(
            test_workspace.id, chat_session.id, "again", execution.id
        ):
            pass

        history = graph.payloads[1]["messages"]
        assert [type(m).__name__ for m in history] == [
            "HumanMessage",
            "AIMessage",
            "HumanMessage",
        ]
        assert history[-1].content == "again"
        assert history[1].content == "Hello"

    @pytest.mark.asyncio
    async def test_abort_keeps_partial_text_as_stopped(
        self, db_session, session_factory, test_workspace, monkeypatch, encryption_key
    ):
        agent, chat_session, execution = await _setup(db_session, test_workspace)
        graph = FakeGraphV2()
        _install(monkeypatch, session_factory, graph)

        gen = stream_turn(test_workspace.id, chat_session.id, "hi", execution.id)
        seen_token = False
        async for event in gen:
            if event["event"] == "token":
                seen_token = True
                break
        assert seen_token
        await gen.aclose()

        async with session_factory() as check:
            row = (
                (
                    await check.execute(
                        select(ChatMessage).where(
                            ChatMessage.session_id == chat_session.id,
                            ChatMessage.role == "assistant",
                        )
                    )
                )
                .scalars()
                .one()
            )
            assert row.status == "stopped"
            assert "Hel" in row.content
            run_row = await check.get(Execution, execution.id)
            assert run_row.status == "cancelled"

    @pytest.mark.asyncio
    async def test_error_deletes_empty_assistant_row(
        self, db_session, session_factory, test_workspace, monkeypatch, encryption_key
    ):
        from app.services.agent_runtime import AgentRuntimeError

        agent, chat_session, execution = await _setup(db_session, test_workspace)

        async def explode(*a, **k):
            raise AgentRuntimeError("no profile")

        monkeypatch.setattr("app.services.agent_runtime.async_session", session_factory)
        monkeypatch.setattr("app.services.agent_runtime.build_graph", explode)

        events = [
            event
            async for event in stream_turn(
                test_workspace.id, chat_session.id, "hi", execution.id
            )
        ]
        assert events[-1]["event"] == "error"

        async with session_factory() as check:
            assistant = (
                (
                    await check.execute(
                        select(ChatMessage).where(
                            ChatMessage.session_id == chat_session.id,
                            ChatMessage.role == "assistant",
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert assistant == []
            user = (
                (
                    await check.execute(
                        select(ChatMessage).where(
                            ChatMessage.session_id == chat_session.id,
                            ChatMessage.role == "user",
                        )
                    )
                )
                .scalars()
                .one()
            )
            assert user.content == "hi"
            run_row = await check.get(Execution, execution.id)
            assert run_row.status == "failed"

    @pytest.mark.asyncio
    async def test_activity_and_reasoning_are_capped(
        self, db_session, session_factory, test_workspace, monkeypatch, encryption_key
    ):
        agent, chat_session, execution = await _setup(db_session, test_workspace)

        class BloatedGraph:
            async def astream_events(self, payload, version):
                yield {
                    "event": "on_tool_start",
                    "run_id": "r1",
                    "name": "read_skill",
                    "metadata": {},
                    "data": {"input": {"name": "big"}},
                }
                yield {
                    "event": "on_tool_end",
                    "run_id": "r1",
                    "name": "read_skill",
                    "metadata": {},
                    "data": {"output": "x" * 1_000_000},
                }
                yield {
                    "event": "on_chat_model_stream",
                    "metadata": {},
                    "data": {
                        "chunk": AIMessageChunk(
                            content="ok",
                            additional_kwargs={"reasoning_content": "y" * 100_000},
                        )
                    },
                }
                yield {
                    "event": "on_chain_end",
                    "name": "LangGraph",
                    "parent_ids": [],
                    "metadata": {},
                    "data": {"output": {"messages": [AIMessage(content="ok")]}},
                }

        _install(monkeypatch, session_factory, BloatedGraph())
        events = [
            event
            async for event in stream_turn(
                test_workspace.id, chat_session.id, "hi", execution.id
            )
        ]
        done = events[-1]
        assert done["event"] == "done"

        async with session_factory() as check:
            row = (
                (
                    await check.execute(
                        select(ChatMessage).where(
                            ChatMessage.session_id == chat_session.id,
                            ChatMessage.role == "assistant",
                        )
                    )
                )
                .scalars()
                .one()
            )
            assert len(row.reasoning) <= 32_000 + 32
            for event in row.activity:
                for key in ("args", "result"):
                    if event.get(key) is not None:
                        assert len(json.dumps(event[key])) <= 8_000 + 32

    @pytest.mark.asyncio
    async def test_files_staged_event(
        self, db_session, session_factory, test_workspace, monkeypatch, encryption_key
    ):
        agent, chat_session, execution = await _setup(db_session, test_workspace)
        graph = FakeGraphV2()
        _install(monkeypatch, session_factory, graph)
        async def fake_stage(documents):
            return None, ["a.csv", "b.csv"]

        monkeypatch.setattr(
            "app.services.agent_runtime._stage_files", fake_stage
        )

        events = [
            event
            async for event in stream_turn(
                test_workspace.id, chat_session.id, "hi", execution.id
            )
        ]
        staged = [
            e["data"]
            for e in events
            if e["event"] == "activity" and e["data"]["type"] == "files_staged"
        ]
        assert staged == [{"type": "files_staged", "names": ["a.csv", "b.csv"]}]

    @pytest.mark.asyncio
    async def test_live_config_reread_between_turns(
        self, db_session, session_factory, test_workspace, monkeypatch, encryption_key
    ):
        agent, chat_session, execution = await _setup(db_session, test_workspace)
        graph = FakeGraphV2()
        prompts_seen: list[str] = []

        def capture_build(validated, agent_row, tools, *, streaming):
            prompts_seen.append(agent_row.system_prompt)
            return graph

        monkeypatch.setattr("app.services.agent_runtime.async_session", session_factory)
        monkeypatch.setattr(
            "app.services.agent_runtime.build_graph", capture_build
        )

        async for _ in stream_turn(
            test_workspace.id, chat_session.id, "hi", execution.id
        ):
            pass

        agent.system_prompt = "New instructions."
        db_session.add(agent)
        await db_session.commit()

        async for _ in stream_turn(
            test_workspace.id, chat_session.id, "again", execution.id
        ):
            pass

        assert prompts_seen == ["Be brief.", "New instructions."]

    @pytest.mark.asyncio
    async def test_event_count_cap(
        self, db_session, session_factory, test_workspace, monkeypatch, encryption_key
    ):
        agent, chat_session, execution = await _setup(db_session, test_workspace)

        class ChattyGraph:
            async def astream_events(self, payload, version):
                for index in range(250):
                    yield {
                        "event": "on_tool_start",
                        "run_id": f"r{index}",
                        "name": "read_skill",
                        "metadata": {},
                        "data": {"input": {"name": f"s{index}"}},
                    }
                    yield {
                        "event": "on_tool_end",
                        "run_id": f"r{index}",
                        "name": "read_skill",
                        "metadata": {},
                        "data": {"output": "ok"},
                    }
                yield {
                    "event": "on_chain_end",
                    "name": "LangGraph",
                    "parent_ids": [],
                    "metadata": {},
                    "data": {"output": {"messages": [AIMessage(content="done")]}},
                }

        _install(monkeypatch, session_factory, ChattyGraph())
        events = [
            event
            async for event in stream_turn(
                test_workspace.id, chat_session.id, "hi", execution.id
            )
        ]
        assert events[-1]["event"] == "done"

        async with session_factory() as check:
            row = (
                (
                    await check.execute(
                        select(ChatMessage).where(
                            ChatMessage.session_id == chat_session.id,
                            ChatMessage.role == "assistant",
                        )
                    )
                )
                .scalars()
                .one()
            )
            assert len(row.activity) <= 200
