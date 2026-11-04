"""Agent data-source attachments (D4): allowlist per agent, full-replace save,
empty allowlist rejected, delete-attached-connection 409.

The connection rows are created directly on the model (their CRUD is covered in
`test_external_databases_*.py`); these tests exercise the agent-side contract.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.crypto import encrypt_api_key
from app.models.agent import AgentDataSource
from app.models.external_database import ExternalDatabaseConnection

from unit_tests.test_agents_router import make_profile, payload, url


@pytest.fixture(autouse=True)
def fixed_model_profile(monkeypatch):
    """Same capability stub as test_agents_router — no test touches models.dev."""
    monkeypatch.setattr(
        "app.services.agent_capabilities.lookup_profile",
        lambda provider, model_id: {
            "max_output_tokens": 4096,
            "reasoning_effort_levels": ["low", "medium", "high"],
        },
    )


@pytest_asyncio.fixture
async def profile(db_session, test_workspace):
    return await make_profile(db_session, test_workspace.id)


@pytest_asyncio.fixture
async def postgres_connection(db_session, test_workspace):
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


@pytest_asyncio.fixture
async def mongo_connection(db_session, test_workspace):
    row = ExternalDatabaseConnection(
        workspace_id=test_workspace.id,
        name="Docs Mongo",
        kind="mongodb",
        encrypted_uri=encrypt_api_key("mongodb://localhost:27017"),
        database_name="docs",
        collection_name="pages",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


async def _make_agent(client, test_workspace, auth_headers, profile, **overrides):
    response = await client.post(
        url(test_workspace.id), json=payload(profile.id, **overrides), headers=auth_headers
    )
    return response


async def _rows(db_session, agent_id: str) -> list[AgentDataSource]:
    result = await db_session.execute(
        select(AgentDataSource).where(AgentDataSource.agent_id == agent_id)
    )
    return list(result.scalars().all())


@pytest.mark.asyncio
async def test_agent_round_trip_with_data_sources(
    client, test_workspace, auth_headers, profile, postgres_connection
):
    created = await _make_agent(
        client,
        test_workspace,
        auth_headers,
        profile,
        data_sources=[{"id": postgres_connection.id, "tables": ["public.users", "public.orders"]}],
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["data_sources"] == [
        {"id": postgres_connection.id, "name": "Analytics DB", "tables": ["public.users", "public.orders"]}
    ]
    assert body["status"] == "ready"


@pytest.mark.asyncio
async def test_empty_table_list_is_rejected(
    client, test_workspace, auth_headers, profile, postgres_connection
):
    response = await _make_agent(
        client,
        test_workspace,
        auth_headers,
        profile,
        data_sources=[{"id": postgres_connection.id, "tables": []}],
    )
    assert response.status_code == 422
    # The schema's min_length guard fires first; the loc path runs through data_sources.
    assert "data_sources" in str(response.json()["detail"][0]["loc"])


@pytest.mark.asyncio
async def test_unknown_connection_is_rejected(
    client, test_workspace, auth_headers, profile
):
    response = await _make_agent(
        client,
        test_workspace,
        auth_headers,
        profile,
        data_sources=[{"id": "no-such-connection", "tables": ["public.users"]}],
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "data_sources"


@pytest.mark.asyncio
async def test_non_queryable_kind_is_rejected(
    client, test_workspace, auth_headers, profile, db_session
):
    # Chroma is the only kind left without an executor (addendum 2026-11-05
    # made mysql and mongodb queryable).
    row = ExternalDatabaseConnection(
        workspace_id=test_workspace.id,
        name="Vector Store",
        kind="chromadb",
        encrypted_uri=encrypt_api_key("http://localhost:8000/api/v1"),
        collection_name="pages",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    response = await _make_agent(
        client,
        test_workspace,
        auth_headers,
        profile,
        data_sources=[{"id": row.id, "tables": ["pages"]}],
    )
    assert response.status_code == 422
    assert "queryable" in response.json()["detail"][0]["msg"]


@pytest.mark.asyncio
async def test_other_workspaces_connections_are_not_reachable(
    client, db_session, auth_headers, profile, test_workspace, test_user
):
    from app.models.workspace import Workspace

    other = Workspace(name="Other WS", owner_id=test_user.id)
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)

    foreign = ExternalDatabaseConnection(
        workspace_id=other.id,
        name="Foreign DB",
        kind="postgres",
        encrypted_uri=encrypt_api_key("postgresql://x@y/z"),
        database_name="z",
    )
    db_session.add(foreign)
    await db_session.commit()
    await db_session.refresh(foreign)

    response = await _make_agent(
        client,
        test_workspace,
        auth_headers,
        profile,
        data_sources=[{"id": foreign.id, "tables": ["public.t"]}],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_fully_replaces_attachments(
    client, db_session, test_workspace, auth_headers, profile, postgres_connection, mongo_connection
):
    created = await _make_agent(
        client,
        test_workspace,
        auth_headers,
        profile,
        data_sources=[{"id": postgres_connection.id, "tables": ["public.users"]}],
    )
    agent_id = created.json()["id"]

    # A second postgres connection to swap in.
    replacement = ExternalDatabaseConnection(
        workspace_id=test_workspace.id,
        name="Warehouse",
        kind="postgres",
        encrypted_uri=encrypt_api_key("postgresql://imyuvi@localhost:5432/warehouse"),
        database_name="warehouse",
    )
    db_session.add(replacement)
    await db_session.commit()
    await db_session.refresh(replacement)

    updated = await client.put(
        f"{url(test_workspace.id)}/{agent_id}",
        json=payload(
            profile.id,
            data_sources=[{"id": replacement.id, "tables": ["public.facts"]}],
        ),
        headers=auth_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data_sources"] == [
        {"id": replacement.id, "name": "Warehouse", "tables": ["public.facts"]}
    ]

    rows = await _rows(db_session, agent_id)
    assert len(rows) == 1
    assert rows[0].connection_id == replacement.id
    assert rows[0].tables == ["public.facts"]


@pytest.mark.asyncio
async def test_deleting_an_attached_connection_is_409(
    client, test_workspace, auth_headers, profile, postgres_connection
):
    created = await _make_agent(
        client,
        test_workspace,
        auth_headers,
        profile,
        data_sources=[{"id": postgres_connection.id, "tables": ["public.users"]}],
    )
    agent_name = created.json()["name"]

    blocked = await client.delete(
        f"/api/workspaces/{test_workspace.id}/external-databases/{postgres_connection.id}",
        headers=auth_headers,
    )
    assert blocked.status_code == 409
    assert agent_name in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_deleting_an_unattached_connection_succeeds(
    client, test_workspace, auth_headers, postgres_connection
):
    response = await client.delete(
        f"/api/workspaces/{test_workspace.id}/external-databases/{postgres_connection.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
