"""The runtime's model and tool building, and the chat stream's execution record.

No provider and no sandbox: the graph is scripted, capability lookup is fixed, and
the sandbox never starts because no tool is invoked.
"""

import pytest
from cryptography.fernet import Fernet
from langchain_core.messages import AIMessage, AIMessageChunk

from app.config import get_settings
from app.crypto import encrypt_api_key
from app.models.agent import Agent
from app.models.execution import Execution
from app.models.knowledge import DOCUMENT_STATUS_STORED, Document, FileFolder
from app.models.llm_profile import LlmProfile
from app.models.skill import Skill
from app.models.tool import Tool
from app.services.agent_composition import AgentInput, validate_agent
from app.services.agent_runtime import (
    AgentRuntimeError,
    _cost,
    build_chat_model,
    build_tools,
    stream_chat,
)
from app.services.sandbox import InMemoryToolSource, SandboxSession

AGENT_CODE = '''def weather(city: str) -> str:
    """Look up the weather.

    Args:
        city: The city to look up.
    """
    return city
'''


@pytest.fixture(autouse=True)
def fixed_model_profile(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_capabilities.lookup_profile",
        lambda provider, model_id: {"max_output_tokens": 4096},
    )


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


class TestModelBuilding:
    def test_parameters_are_mapped_per_provider(self, monkeypatch, encryption_key):
        captured = {}

        def fake_init(target, **kwargs):
            captured["target"] = target
            captured["kwargs"] = kwargs
            return object()

        monkeypatch.setattr("app.services.agent_runtime.init_chat_model", fake_init)
        params = {
            "temperature": 0.4,
            "max_tokens": 2048,
            "top_p": 0.9,
            "seed": 3,
            "stop": ["END"],
            "reasoning": "high",
            "streaming": True,
        }

        for provider, token_key, stop_key in (
            ("openai", "max_tokens", "stop"),
            ("anthropic", "max_tokens", "stop_sequences"),
            ("gemini", "max_output_tokens", "stop"),
        ):
            profile = make_profile("w")
            profile.provider = provider
            build_chat_model(profile, params)

            assert captured["target"].endswith(":gpt-4o-mini")
            assert captured["kwargs"][token_key] == 2048
            assert captured["kwargs"][stop_key] == ["END"]
            assert captured["kwargs"]["temperature"] == 0.4
            assert captured["kwargs"]["reasoning_effort"] == "high"
            assert captured["kwargs"]["streaming"] is True

    def test_a_custom_profile_uses_its_base_url(self, monkeypatch, encryption_key):
        captured = {}

        def fake_init(target, **kwargs):
            captured["target"] = target
            captured["kwargs"] = kwargs
            return object()

        monkeypatch.setattr("app.services.agent_runtime.init_chat_model", fake_init)
        profile = make_profile("w")
        profile.provider = "custom"
        profile.base_url = "http://localhost:11434/v1"

        build_chat_model(profile, {})

        assert captured["target"].startswith("openai:")
        assert captured["kwargs"]["base_url"] == "http://localhost:11434/v1"


class TestToolBuilding:
    @pytest.mark.asyncio
    async def test_builtins_and_skills_are_exposed(
        self, db_session, test_workspace
    ):
        profile = make_profile(test_workspace.id)
        tool = Tool(workspace_id=test_workspace.id, name="weather", code=AGENT_CODE)
        skill = Skill(
            workspace_id=test_workspace.id,
            name="Timekeeper",
            description="Knows the time",
            content="Use /current_time.",
        )
        folder = FileFolder(workspace_id=test_workspace.id, name="Handbook")
        db_session.add_all([profile, tool, skill, folder])
        await db_session.commit()
        await db_session.refresh(folder)
        document = Document(
            workspace_id=test_workspace.id,
            folder_id=folder.id,
            filename="handbook.txt",
            file_url="workspaces/x/files/y",
            file_size=10,
            mime_type="text/plain",
            status=DOCUMENT_STATUS_STORED,
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        validated = await validate_agent(
            db_session,
            test_workspace.id,
            AgentInput(
                name="A",
                description=None,
                llm_profile_id=profile.id,
                system_prompt="You help.",
                source_prompt_id=None,
                params={},
                structured_output_id=None,
                web_search=None,
                skill_ids=[skill.id],
                tool_ids=[tool.id],
                documents=[document.id],
            ),
            agent_id=None,
        )
        session = SandboxSession(tools=InMemoryToolSource({tool.name: tool.code}))

        tools = await build_tools(
            db_session,
            test_workspace.id,
            validated,
            session,
            depth=0,
            filenames=["handbook.txt"],
        )
        names = [tool["name"] if isinstance(tool, dict) else tool.name for tool in tools]

        assert set(names) == {"weather", "current_time", "read_skill", "execute_python"}

    @pytest.mark.asyncio
    async def test_a_provider_native_search_spec_survives_tool_dedupe(
        self, db_session, test_workspace
    ):
        profile = make_profile(test_workspace.id)
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)

        validated = await validate_agent(
            db_session,
            test_workspace.id,
            AgentInput(
                name="Searcher",
                description=None,
                llm_profile_id=profile.id,
                system_prompt="Search when needed.",
                source_prompt_id=None,
                params={},
                structured_output_id=None,
                web_search={"enabled": True, "method": "native"},
                skill_ids=[],
                tool_ids=[],
                folders=[],
                documents=[],
            ),
            agent_id=None,
        )
        session = SandboxSession(tools=InMemoryToolSource({}))

        tools = await build_tools(db_session, test_workspace.id, validated, session, depth=0)

        assert {"type": "web_search"} in tools


class TestCost:
    def test_cache_reads_are_priced_separately(self, encryption_key):
        profile = make_profile("w")
        usage = {
            "input_tokens": 1_000_000,
            "output_tokens": 100_000,
            "total_tokens": 1_100_000,
            "cache_read_tokens": 250_000,
        }
        assert _cost(profile, usage) == pytest.approx(2.625)


class FakeGraph:
    async def astream_events(self, payload, version):
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
        # A nested graph's tokens must not leak into the parent's answer.
        yield {
            "event": "on_chat_model_stream",
            "metadata": {"langgraph_checkpoint_ns": "tools:1|model:2"},
            "data": {"chunk": AIMessageChunk(content="SECRET")},
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


class TestChatStream:
    @pytest.mark.asyncio
    async def test_tokens_and_the_execution_are_recorded(
        self, db_session, session_factory, test_workspace, monkeypatch, encryption_key
    ):
        profile = make_profile(test_workspace.id)
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        agent = Agent(
            workspace_id=test_workspace.id,
            name="Chatty",
            llm_profile_id=profile.id,
            system_prompt="Be brief.",
            params={},
        )
        db_session.add(agent)
        await db_session.commit()
        execution = Execution(
            workspace_id=test_workspace.id,
            agent_id=agent.id,
            status="running",
            trigger_type="chat",
            input_data={"messages": [{"role": "user", "content": "hi"}]},
        )
        db_session.add(execution)
        await db_session.commit()

        monkeypatch.setattr("app.services.agent_runtime.async_session", session_factory)
        monkeypatch.setattr(
            "app.services.agent_runtime.build_graph", lambda *a, **k: FakeGraph()
        )

        events = [
            event
            async for event in stream_chat(
                test_workspace.id,
                agent.id,
                [{"role": "user", "content": "hi"}],
                execution.id,
            )
        ]

        tokens = [event["data"]["delta"] for event in events if event["event"] == "token"]
        assert tokens == ["Hel", "lo"]
        done = [event for event in events if event["event"] == "done"][0]
        assert done["data"]["usage"]["input_tokens"] == 10
        assert done["data"]["cost_usd"] == pytest.approx(0.000034)

        async with session_factory() as check:
            row = await check.get(Execution, execution.id)
            assert row.status == "completed"
            assert row.output_data["content"] == "Hello"
            assert row.token_usage["output_tokens"] == 2
            assert float(row.cost_usd) == pytest.approx(0.000034)
            assert row.completed_at is not None

    @pytest.mark.asyncio
    async def test_a_failed_build_marks_the_execution_failed(
        self, db_session, session_factory, test_workspace, monkeypatch, encryption_key
    ):
        profile = make_profile(test_workspace.id)
        db_session.add(profile)
        await db_session.commit()
        await db_session.refresh(profile)
        agent = Agent(
            workspace_id=test_workspace.id,
            name="Broken",
            llm_profile_id=profile.id,
            system_prompt="Hi",
            params={},
        )
        db_session.add(agent)
        await db_session.commit()
        execution = Execution(
            workspace_id=test_workspace.id,
            agent_id=agent.id,
            status="running",
            trigger_type="chat",
        )
        db_session.add(execution)
        await db_session.commit()

        monkeypatch.setattr("app.services.agent_runtime.async_session", session_factory)

        def explode(*args, **kwargs):
            raise AgentRuntimeError("the provider key is gone")

        monkeypatch.setattr("app.services.agent_runtime.build_graph", explode)

        events = [
            event
            async for event in stream_chat(
                test_workspace.id, agent.id, [{"role": "user", "content": "hi"}], execution.id
            )
        ]

        assert events[0]["event"] == "error"
        assert "provider key" in events[0]["data"]["detail"]
        async with session_factory() as check:
            row = await check.get(Execution, execution.id)
            assert row.status == "failed"
            assert "provider key" in row.error_message
