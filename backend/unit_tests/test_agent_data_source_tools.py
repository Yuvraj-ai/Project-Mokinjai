"""Host-side data-source tools wired into the agent runtime (D2, D4, D6).

The dials are mocked at the executor boundary; the guard and the allowlist
contract are covered in test_sql_guard.py / test_postgres_source.py.
"""

import json

import pytest
import pytest_asyncio
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from app.crypto import encrypt_api_key
from app.models.external_database import ExternalDatabaseConnection
from app.services.agent_composition import AgentInput, DataSourceRule, validate_agent
from app.services.agent_runtime import build_tools
from app.services.sandbox.session import SandboxSession
from app.services.sandbox.tools import InMemoryToolSource

AGENT_CODE = "def noop() -> str:\n    'Does nothing.'\n    return 'ok'\n"


@pytest_asyncio.fixture
async def connection(db_session, test_workspace):
    row = ExternalDatabaseConnection(
        workspace_id=test_workspace.id,
        name="Analytics DB",
        kind="postgres",
        encrypted_uri=encrypt_api_key("postgresql://imyuvi@localhost:5432/mokinjay_test"),
        database_name="mokinjay_test",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


async def _build(db_session, test_workspace, connection, agent_id: str | None = None):
    from unit_tests.test_agent_runtime import make_profile

    profile = make_profile(test_workspace.id)
    db_session.add(profile)
    await db_session.commit()

    validated = await validate_agent(
        db_session,
        test_workspace.id,
        AgentInput(
            name="Data Agent",
            description=None,
            llm_profile_id=profile.id,
            system_prompt="You answer from the database.",
            source_prompt_id=None,
            params={},
            structured_output_id=None,
            web_search=None,
            data_sources=[DataSourceRule(id=connection.id, tables=["public.users"])],
        ),
        agent_id=agent_id,
    )
    session = SandboxSession(tools=InMemoryToolSource({}))
    tools = await build_tools(db_session, test_workspace.id, validated, session, depth=0)
    return tools, validated


@pytest.mark.asyncio
async def test_both_data_source_tools_are_exposed(db_session, test_workspace, connection):
    tools, _ = await _build(db_session, test_workspace, connection)
    names = {tool["name"] if isinstance(tool, dict) else tool.name for tool in tools}
    assert {"query_data_source", "describe_data_source"} <= names


@pytest.mark.asyncio
async def test_query_tool_runs_through_the_stored_allowlist(
    db_session, test_workspace, connection, monkeypatch
):
    import app.services.agent_tools as agent_tools

    captured: dict = {}

    async def fake_run(uri, sql, allowed_tables, **kwargs):
        captured.update(uri=uri, sql=sql, allowed_tables=list(allowed_tables), kwargs=kwargs)
        from app.services.data_sources.types import QueryResult

        return QueryResult(
            columns=["id"], rows=[[1]], row_count=1, truncated=False, duration_ms=3
        )

    monkeypatch.setattr(agent_tools, "run", fake_run)

    tools, _ = await _build(db_session, test_workspace, connection)
    tool = next(t for t in tools if isinstance(t, BaseTool) and t.name == "query_data_source")
    output = await tool.coroutine(connection_id=connection.id, sql="SELECT id FROM users")

    assert captured["allowed_tables"] == ["public.users"]
    assert "postgresql://imyuvi@localhost" in captured["uri"], "the decrypted URI is used"
    payload = json.loads(output)
    assert payload["columns"] == ["id"]
    assert payload["rows"] == [[1]]
    assert payload["truncated"] is False


@pytest.mark.asyncio
async def test_query_tool_refuses_an_unknown_connection_id(
    db_session, test_workspace, connection
):
    tools, _ = await _build(db_session, test_workspace, connection)
    tool = next(t for t in tools if isinstance(t, BaseTool) and t.name == "query_data_source")
    output = await tool.coroutine(connection_id="other-id", sql="SELECT 1 FROM users")
    assert "unknown" in output.lower()


@pytest.mark.asyncio
async def test_query_tool_surfaces_guard_refusals(
    db_session, test_workspace, connection, monkeypatch
):
    import app.services.agent_tools as agent_tools

    async def boom(*args, **kwargs):
        raise AssertionError("run() must not be called for a refused query")

    monkeypatch.setattr(agent_tools, "run", boom)

    from app.services.data_sources.guard import GuardError

    async def fake_run(uri, sql, allowed_tables, **kwargs):
        raise GuardError("the table private.secrets is not part of this agent's data sources", sql)

    monkeypatch.setattr(agent_tools, "run", fake_run)

    tools, _ = await _build(db_session, test_workspace, connection)
    tool = next(t for t in tools if isinstance(t, BaseTool) and t.name == "query_data_source")
    output = await tool.coroutine(connection_id=connection.id, sql="SELECT * FROM private.secrets")
    assert "refused" in output.lower()
    assert "private.secrets" in output


@pytest.mark.asyncio
async def test_describe_tool_returns_the_schema(
    db_session, test_workspace, connection, monkeypatch
):
    import app.services.agent_tools as agent_tools
    from app.services.data_sources.types import Column, Table

    async def fake_describe(uri, **kwargs):
        return [Table(schema="public", name="users", columns=[
            Column(name="id", type="integer", nullable=False)
        ])]

    monkeypatch.setattr(agent_tools, "describe", fake_describe)

    tools, _ = await _build(db_session, test_workspace, connection)
    tool = next(
        t for t in tools if isinstance(t, BaseTool) and t.name == "describe_data_source"
    )
    output = await tool.coroutine(connection_id=connection.id)
    payload = json.loads(output)
    assert payload["tables"][0]["name"] == "users"
    assert payload["tables"][0]["columns"][0]["type"] == "integer"


@pytest.mark.asyncio
async def test_system_prompt_lists_the_connections(db_session, test_workspace, connection):
    tools, validated = await _build(db_session, test_workspace, connection)
    from app.services.agent_runtime import _system_prompt

    prompt = _system_prompt("You help.", validated)
    assert "Analytics DB" in prompt
    assert connection.id in prompt
    assert "public.users" in prompt


@pytest.mark.asyncio
async def test_audit_context_carries_the_agent_id(
    db_session, test_workspace, connection, monkeypatch
):
    """D3 layer 5: the audit line must name the agent that issued the query."""
    import app.services.agent_tools as agent_tools

    captured: dict = {}

    async def fake_run(uri, sql, allowed_tables, **kwargs):
        captured.update(kwargs)
        from app.services.data_sources.types import QueryResult

        return QueryResult(columns=[], rows=[], row_count=0, truncated=False, duration_ms=0)

    monkeypatch.setattr(agent_tools, "run", fake_run)

    tools, _ = await _build(db_session, test_workspace, connection, agent_id="agent-42")
    tool = next(t for t in tools if isinstance(t, BaseTool) and t.name == "query_data_source")
    await tool.coroutine(connection_id=connection.id, sql="SELECT id FROM users")
    assert captured.get("agent_id") == "agent-42", "the agent id rides along for the audit log"
