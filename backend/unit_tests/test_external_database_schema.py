"""The schema introspection endpoint (D6): RBAC, shape, SSRF blocklist,
TTL cache with PATCH invalidation, sanitized failures.

`describe` is mocked — the real dial is covered in test_postgres_source.py.
"""

import pytest
import pytest_asyncio
from app.services.data_sources.postgres import DataSourceError
from app.services.data_sources.types import Column, Table

pytestmark = pytest.mark.asyncio


def url(workspace_id: str, connection_id: str = "") -> str:
    return f"/api/workspaces/{workspace_id}/external-databases/{connection_id}"


def schema_url(workspace_id: str, connection_id: str) -> str:
    return url(workspace_id, connection_id) + "/schema"


_FAKED = [
    Table(
        schema="public",
        name="users",
        columns=[Column(name="id", type="integer", nullable=False)],
    )
]


@pytest.fixture
def fake_describe(monkeypatch):
    calls: list[str] = []

    async def _describe(uri, **kwargs):
        calls.append(uri)
        return _FAKED

    monkeypatch.setattr("app.routers.external_databases.describe", _describe)
    return calls


@pytest.fixture(autouse=True)
def _fresh_cache():
    from app.services.data_sources.schema_cache import _CACHE

    _CACHE.clear()
    yield
    _CACHE.clear()


@pytest_asyncio.fixture
async def postgres_connection(db_session, test_workspace):
    from app.crypto import encrypt_api_key
    from app.models.external_database import ExternalDatabaseConnection

    row = ExternalDatabaseConnection(
        workspace_id=test_workspace.id,
        name="Analytics DB",
        kind="postgres",
        encrypted_uri=encrypt_api_key("postgresql://imyuvi@localhost:5432/somedb"),
        database_name="somedb",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)
    return row


async def test_editor_gets_the_schema(
    client, test_workspace, auth_headers, postgres_connection, fake_describe
):
    response = await client.get(
        schema_url(test_workspace.id, postgres_connection.id), headers=auth_headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tables"] == [
        {
            "schema": "public",
            "name": "users",
            "columns": [{"name": "id", "type": "integer", "nullable": False}],
        }
    ]
    assert body["fetched_at"]


async def test_viewer_is_forbidden(
    client, test_workspace, viewer_headers, postgres_connection, fake_describe
):
    response = await client.get(
        schema_url(test_workspace.id, postgres_connection.id), headers=viewer_headers
    )
    assert response.status_code == 403


async def test_missing_connection_is_404(
    client, test_workspace, auth_headers, fake_describe
):
    response = await client.get(
        url(test_workspace.id, "no-such-connection"), headers=auth_headers
    )
    assert response.status_code == 404


async def test_metadata_endpoints_are_refused_without_a_dial(
    client, db_session, test_workspace, auth_headers, fake_describe
):
    from app.crypto import encrypt_api_key
    from app.models.external_database import ExternalDatabaseConnection

    for host in (
        "169.254.169.254",
        "fd00:ec2::254",
        "metadata.google.internal",
        "100.100.100.200",
    ):
        row = ExternalDatabaseConnection(
            workspace_id=test_workspace.id,
            name=f"meta-{host}",
            kind="postgres",
            encrypted_uri=encrypt_api_key(f"postgresql://user@{host}:5432/db"),
            database_name="db",
        )
        db_session.add(row)
        await db_session.commit()
        await db_session.refresh(row)

        response = await client.get(
            schema_url(test_workspace.id, row.id), headers=auth_headers
        )
        assert response.status_code == 400, f"{host} must be refused"
        assert not fake_describe, "a blocked host must never be dialled"

        await db_session.delete(row)
        await db_session.commit()


async def test_private_ranges_are_allowed(
    client, test_workspace, auth_headers, postgres_connection, fake_describe
):
    response = await client.get(
        schema_url(test_workspace.id, postgres_connection.id), headers=auth_headers
    )
    assert response.status_code == 200


async def test_schema_is_cached_and_patch_invalidates(
    client, test_workspace, auth_headers, postgres_connection, fake_describe
):
    first = await client.get(schema_url(test_workspace.id, postgres_connection.id), headers=auth_headers)
    second = await client.get(schema_url(test_workspace.id, postgres_connection.id), headers=auth_headers)
    assert len(fake_describe) == 1, "the second call must hit the 60s cache"
    assert second.json() == first.json()

    patched = await client.patch(
        url(test_workspace.id, postgres_connection.id),
        json={"name": "Renamed DB"},
        headers=auth_headers,
    )
    assert patched.status_code == 200

    third = await client.get(schema_url(test_workspace.id, postgres_connection.id), headers=auth_headers)
    assert len(fake_describe) == 2, "a PATCH must invalidate the cached schema"
    assert third.status_code == 200


async def test_connection_failure_is_sanitized(
    client, test_workspace, auth_headers, postgres_connection, monkeypatch
):
    async def _fail(uri, **kwargs):
        raise DataSourceError("could not connect to the external database")

    monkeypatch.setattr("app.routers.external_databases.describe", _fail)

    response = await client.get(
        schema_url(test_workspace.id, postgres_connection.id), headers=auth_headers
    )
    assert response.status_code == 502
    assert "postgresql://" not in response.json()["detail"]
    assert "somedb" not in response.json()["detail"]
