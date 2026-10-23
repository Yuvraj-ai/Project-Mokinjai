"""Slice 1: the agent schema and its composition tables.

These tests exercise the models directly (not the API): they pin the columns the
API will rely on, the join-table keys, and the two guards that must live in the
database rather than only in a router — case-insensitive agent names and a
self-referencing subagent.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.agent import Agent, AgentConnector, AgentSkill, AgentSubagent
from app.models.connector import ConnectorInstance
from app.models.execution import Execution
from app.models.knowledge import FileFolder
from app.models.llm_profile import LlmProfile
from app.models.resource_usage import ResourceUsage, bump_usage
from app.models.search_credential import SearchCredential
from app.models.skill import Skill
from app.models.structured_output import StructuredOutput
from app.models.tool import Tool


async def _workspace_llm_profile(db_session, workspace_id):
    profile = LlmProfile(
        workspace_id=workspace_id,
        name="Profile",
        provider="openai",
        model_id="gpt-4o-mini",
        encrypted_api_key=b"ciphertext",
        context_window=128000,
        compaction_at_tokens=102400,
        input_price_per_million=0.15,
        output_price_per_million=0.6,
        cache_price_per_million=0.0,
        status="verified",
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


class TestAgentModel:
    @pytest.mark.asyncio
    async def test_create_agent_with_parameters(self, db_session, test_workspace, test_user):
        profile = await _workspace_llm_profile(db_session, test_workspace.id)
        agent = Agent(
            workspace_id=test_workspace.id,
            name="Support Agent",
            description="Answers support questions",
            llm_profile_id=profile.id,
            system_prompt="You are helpful.",
            params={"temperature": 0.4, "max_tokens": 2048, "streaming": False},
            web_search={"enabled": False},
            created_by=test_user.id,
        )
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        assert agent.id is not None
        assert agent.name == "Support Agent"
        assert agent.params["max_tokens"] == 2048
        assert agent.llm_profile_id == profile.id
        assert agent.structured_output_id is None
        assert agent.source_prompt_id is None

    @pytest.mark.asyncio
    async def test_agent_name_is_unique_per_workspace_case_insensitively(
        self, db_session, test_workspace
    ):
        db_session.add(Agent(workspace_id=test_workspace.id, name="Support", system_prompt="x"))
        await db_session.commit()

        db_session.add(Agent(workspace_id=test_workspace.id, name="support", system_prompt="y"))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_same_name_is_allowed_in_another_workspace(
        self, db_session, test_workspace, test_user
    ):
        from app.models.workspace import Workspace

        other = Workspace(name="Other", owner_id=test_user.id)
        db_session.add(other)
        await db_session.commit()

        db_session.add(Agent(workspace_id=test_workspace.id, name="Support", system_prompt="x"))
        db_session.add(Agent(workspace_id=other.id, name="Support", system_prompt="y"))
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_agent_composition_joins(self, db_session, test_workspace):
        agent = Agent(workspace_id=test_workspace.id, name="Composed", system_prompt="x")
        skill = Skill(
            workspace_id=test_workspace.id,
            name="SkillA",
            description="A",
            content="Body",
        )
        tool = Tool(workspace_id=test_workspace.id, name="tool_a", code="def tool_a():\n    return 1")
        kb = FileFolder(workspace_id=test_workspace.id, name="KB")
        connector = ConnectorInstance(
            workspace_id=test_workspace.id,
            connector_type="github",
            name="GitHub",
            status="enabled",
            config={},
            tool_names=[],
        )
        db_session.add_all([agent, skill, tool, kb, connector])
        await db_session.commit()

        db_session.add_all(
            [
                AgentSkill(agent_id=agent.id, skill_id=skill.id),
                AgentConnector(agent_id=agent.id, connector_instance_id=connector.id),
                AgentSubagent(agent_id=agent.id, subagent_id=agent.id),
            ]
        )
        # Self-reference is refused by the database, not only by the router.
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestExecutionAgentLink:
    @pytest.mark.asyncio
    async def test_execution_records_agent_id(self, db_session, test_workspace):
        agent = Agent(workspace_id=test_workspace.id, name="Runner", system_prompt="x")
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
        await db_session.refresh(execution)

        assert execution.agent_id == agent.id
        assert execution.workflow_id is None

    @pytest.mark.asyncio
    async def test_deleting_an_agent_keeps_its_executions(self, db_session, test_workspace):
        agent = Agent(workspace_id=test_workspace.id, name="Runner", system_prompt="x")
        db_session.add(agent)
        await db_session.commit()
        execution = Execution(
            workspace_id=test_workspace.id,
            agent_id=agent.id,
            status="completed",
            trigger_type="chat",
        )
        db_session.add(execution)
        await db_session.commit()

        await db_session.delete(agent)
        await db_session.commit()
        await db_session.refresh(execution)

        assert execution.agent_id is None


class TestLlmProfileOutputCeiling:
    @pytest.mark.asyncio
    async def test_max_output_tokens_defaults_to_none(self, db_session, test_workspace):
        profile = await _workspace_llm_profile(db_session, test_workspace.id)
        assert profile.max_output_tokens is None


class TestSearchCredential:
    @pytest.mark.asyncio
    async def test_one_credential_per_provider_per_workspace(self, db_session, test_workspace):
        db_session.add(
            SearchCredential(
                workspace_id=test_workspace.id,
                provider="tavily",
                encrypted_api_key=b"one",
            )
        )
        await db_session.commit()

        db_session.add(
            SearchCredential(
                workspace_id=test_workspace.id,
                provider="tavily",
                encrypted_api_key=b"two",
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestResourceUsage:
    @pytest.mark.asyncio
    async def test_bump_creates_then_increments(self, db_session, test_workspace):
        resource_id = str(uuid.uuid4())

        await bump_usage(db_session, test_workspace.id, "llm_profile", resource_id)
        await bump_usage(db_session, test_workspace.id, "llm_profile", resource_id)
        await db_session.commit()

        row = await db_session.get(ResourceUsage, (test_workspace.id, "llm_profile", resource_id))
        assert row is not None
        assert row.use_count == 2
        assert row.last_used_at is not None

    @pytest.mark.asyncio
    async def test_usage_is_separate_per_resource_type(self, db_session, test_workspace):
        resource_id = str(uuid.uuid4())
        await bump_usage(db_session, test_workspace.id, "llm_profile", resource_id)
        await bump_usage(db_session, test_workspace.id, "structured_output", resource_id)
        await db_session.commit()

        rows = (
            await db_session.execute(
                ResourceUsage.__table__.select().where(
                    ResourceUsage.workspace_id == test_workspace.id
                )
            )
        ).all()
        assert len(rows) == 2


class TestStructuredOutputLink:
    @pytest.mark.asyncio
    async def test_agent_references_a_structured_output(self, db_session, test_workspace):
        output = StructuredOutput(
            workspace_id=test_workspace.id,
            name="Answer",
            description="A structured answer",
            fields=[{"name": "text", "type": "string", "description": "The answer"}],
        )
        db_session.add(output)
        await db_session.commit()

        agent = Agent(
            workspace_id=test_workspace.id,
            name="Structured",
            system_prompt="x",
            structured_output_id=output.id,
        )
        db_session.add(agent)
        await db_session.commit()
        await db_session.refresh(agent)

        assert agent.structured_output_id == output.id
