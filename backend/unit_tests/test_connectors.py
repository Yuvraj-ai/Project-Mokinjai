"""Connectors — the predefined catalog, the instances, and their secrets.

A connector is a catalog entry a user enables with a credential (ADR-013). Nothing
in this file talks to a live MCP server: the probe is monkeypatched at the router
boundary exactly as `test_llm_profiles.py` monkeypatches `probe_llm`, so every
branch of the API is exercised without a network. Verification against real servers
is manual and is the plan's final task.

**Which connectors exist is a later decision.** The generic tests validate the
*contract* every entry must satisfy; the handful of tests below that name a specific
connector (`github`, `postgres`, `filesystem`, `everything`, `slack`, `notion`) are
**illustrative fixtures** standing in for a kind of connector. If the committed roster
changes, update those fixtures — do not delete the generic tests, which are what hold
the shape.
"""

from app.services.connector_catalog import ENTRIES, get_entry, list_entries


def test_every_entry_declares_the_fields_its_transport_needs():
    for entry in list_entries():
        assert entry.id and entry.display_name and entry.description
        assert entry.transport in {"streamable_http", "stdio"}
        if entry.transport == "streamable_http":
            assert entry.url, f"{entry.id} is a URL transport with no URL"
        else:
            assert entry.command, f"{entry.id} is a stdio transport with no command"
            assert entry.args, f"{entry.id} is a stdio transport with no arguments"


def test_every_api_key_entry_declares_where_the_secret_goes():
    for entry in list_entries():
        if entry.auth_type == "api_key":
            assert entry.auth_header, f"{entry.id} takes an API key with no header name"
            assert entry.secret_label, f"{entry.id} takes an API key with no label"
        if entry.auth_type in {"none", "oauth"}:
            assert entry.secret_label is None, f"{entry.id} asks for a secret it cannot use"


def test_adding_an_entry_needs_nothing_but_the_entry():
    """The shape's whole point: the roster is data, so deciding it can be deferred.

    This asserts the shared contract holds for **every** entry generically, which is
    what makes adding, removing or replacing a connector a data-only change — no
    branch, no column, no migration, no endpoint, no frontend edit. It deliberately
    does **not** pin which entries exist.
    """
    entries = list_entries()
    assert entries, "the catalog must not be empty or nothing can be enabled"

    for entry in entries:
        # Self-describing: a renderer needs nothing beyond the entry itself.
        if entry.auth_type in {"api_key", "connection_string"}:
            assert entry.secret_label, f"{entry.id} takes a secret but does not name it"
        # A transport carries only its own fields; the other set must be empty so a
        # consumer never has to guess which to read.
        if entry.transport == "streamable_http":
            assert entry.url and entry.command is None and not entry.args
        else:
            assert entry.command and entry.args and entry.url is None

    ids = [entry.id for entry in entries]
    assert len(ids) == len(set(ids)), f"duplicate catalog ids: {sorted(ids)}"


# ---------------------------------------------------------------------------
# Illustrative fixtures below this line.
#
# Each names a specific connector to exercise one transport × auth combination.
# They stand in for a *kind* of connector: the committed roster is a later decision,
# so when it changes, update these — the generic tests above are what hold the shape.
# ---------------------------------------------------------------------------


def test_github_is_a_url_entry_authenticated_with_a_bearer_token():
    github = get_entry("github")
    assert github is not None
    assert github.transport == "streamable_http"
    assert github.auth_type == "api_key"
    assert github.url.startswith("https://")
    assert github.auth_header == "Authorization"
    assert github.auth_prefix == "Bearer "


def test_postgres_is_an_stdio_entry_that_needs_a_database_name():
    postgres = get_entry("postgres")
    assert postgres is not None
    assert postgres.transport == "stdio"
    assert postgres.auth_type == "connection_string"
    assert postgres.config_fields == ("database",)
    assert "{secret}" in postgres.args


def test_filesystem_interpolates_a_path_from_the_instance_config():
    filesystem = get_entry("filesystem")
    assert filesystem is not None
    assert filesystem.auth_type == "none"
    assert filesystem.config_fields == ("path",)
    assert "{path}" in filesystem.args


def test_the_two_no_auth_local_servers_are_present_for_verification():
    """These are how the feature is checked without a credential."""
    everything = get_entry("everything")
    filesystem = get_entry("filesystem")
    assert everything is not None and everything.auth_type == "none"
    assert filesystem is not None and filesystem.auth_type == "none"


def test_slack_and_notion_are_declared_with_their_real_auth_type():
    """Both authenticate with OAuth, so both say so instead of pretending."""
    for connector_id in ("slack", "notion"):
        entry = get_entry(connector_id)
        assert entry is not None, f"{connector_id} should be in the catalog"
        assert entry.transport == "streamable_http"
        assert entry.auth_type == "oauth"


def test_an_unknown_connector_type_has_no_entry():
    assert get_entry("no-such-connector") is None
    assert len(ENTRIES) == len(list_entries())


async def test_connector_instance_round_trips_with_its_defaults(db_session, test_workspace):
    from sqlalchemy import select

    from app.models.connector import ConnectorInstance

    instance = ConnectorInstance(
        workspace_id=test_workspace.id,
        connector_type="filesystem",
        name="Project files",
        status="pending",
        config={"path": "/srv/data"},
    )
    db_session.add(instance)
    await db_session.commit()

    found = (
        await db_session.execute(
            select(ConnectorInstance).where(ConnectorInstance.id == instance.id)
        )
    ).scalar_one()

    assert found.auth_scope == "workspace", "the Model B migration point defaults to Model A"
    assert found.auth_encrypted is None, "a connector that takes no secret stores no ciphertext"
    assert found.tool_names == [], "no probe has run yet"
    assert found.last_error is None
    assert found.last_tested_at is None
    assert found.created_at is not None, "created_at should come from the server default"
    assert found.updated_at is not None, "updated_at should come from the server default"


import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.models.connector import ConnectorInstance
from app.services.connector_catalog import get_entry
from app.services.connector_runtime import (
    ConnectorProbeError,
    connection_for,
    connections_for,
    server_config,
    slug,
)


@pytest.fixture
def encryption_key():
    """A throwaway Fernet key for the duration of one test.

    Mirrors the fixture in `test_llm_profiles.py`. It stays here rather than moving to
    conftest because moving it would mean editing a passing file for no functional gain.
    """
    settings = get_settings()
    previous = getattr(settings, "LLM_ENCRYPTION_KEY", "")
    settings.LLM_ENCRYPTION_KEY = Fernet.generate_key().decode()
    yield settings.LLM_ENCRYPTION_KEY
    settings.LLM_ENCRYPTION_KEY = previous


def _instance(connector_type: str, *, secret: str | None = None, config: dict | None = None):
    """A row that was never committed — `connection_for` reads it, never queries it."""
    from app.crypto import encrypt_api_key

    return ConnectorInstance(
        id="11111111-1111-1111-1111-111111111111",
        workspace_id="22222222-2222-2222-2222-222222222222",
        connector_type=connector_type,
        name="Test connector",
        status="pending",
        auth_scope="workspace",
        auth_encrypted=encrypt_api_key(secret) if secret else None,
        config=config or {},
        tool_names=[],
    )


def test_slug_is_lowercase_and_tool_name_safe():
    assert slug("My GitHub") == "my_github"
    assert slug("Everything (test server)") == "everything_test_server"
    assert slug("  ---  ") == "connector", "an empty slug would produce a bare underscore"


def test_a_url_entry_builds_a_bearer_header():
    connection = server_config(get_entry("github"), "ghp-token", {})
    assert connection == {
        "transport": "streamable_http",
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {"Authorization": "Bearer ghp-token"},
    }


def test_a_url_entry_refuses_a_blank_secret():
    with pytest.raises(ConnectorProbeError, match="required"):
        server_config(get_entry("github"), "", {})


def test_an_stdio_entry_interpolates_a_config_value():
    connection = server_config(get_entry("filesystem"), None, {"path": "/tmp/scratch"})
    assert connection["transport"] == "stdio"
    assert connection["command"] == "npx"
    assert connection["args"][-1] == "/tmp/scratch"


def test_an_stdio_entry_names_the_value_it_is_missing():
    with pytest.raises(ConnectorProbeError, match="path"):
        server_config(get_entry("filesystem"), None, {})


def test_a_connection_string_entry_interpolates_the_secret():
    uri = "postgresql://user:pw@localhost:5432/analytics"
    connection = server_config(get_entry("postgres"), uri, {"database": "analytics"})
    assert connection["args"][-1] == uri


def test_connection_for_decrypts_the_stored_secret(encryption_key):
    connection = connection_for(_instance("github", secret="ghp-token"))
    assert connection["headers"]["Authorization"] == "Bearer ghp-token"


def test_connection_for_handles_an_entry_that_takes_no_secret(encryption_key):
    connection = connection_for(_instance("filesystem", config={"path": "/tmp/scratch"}))
    assert connection["args"][-1] == "/tmp/scratch"
    assert "headers" not in connection


def test_connection_for_refuses_a_type_that_left_the_catalog(encryption_key):
    with pytest.raises(ConnectorProbeError, match="no longer in the connector catalog"):
        connection_for(_instance("retired-connector", secret="whatever"))


def test_connections_for_keys_by_instance_id(encryption_key):
    first = _instance("github", secret="ghp-token")
    second = _instance("filesystem", config={"path": "/tmp/scratch"})
    second.id = "33333333-3333-3333-3333-333333333333"

    connections = connections_for([first, second])

    assert set(connections) == {first.id, second.id}
    assert connections[first.id]["transport"] == "streamable_http"
    assert connections[second.id]["transport"] == "stdio"


import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.connector import ConnectorInstance


@pytest_asyncio.fixture(scope="function")
async def service_session(engine):
    """A session the test drives itself, separate from the client's per-request one."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


def _body(**overrides):
    payload = {
        "connector_type": "github",
        "name": "GitHub (main)",
        "auth_secret": "ghp-plain-token",
        "config": {},
    }
    payload.update(overrides)
    return payload


async def test_the_catalog_endpoint_lists_every_entry(client, auth_headers, test_workspace):
    response = await client.get(
        f"/api/workspaces/{test_workspace.id}/connectors/catalog", headers=auth_headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == len(list_entries())
    github = next(entry for entry in body["entries"] if entry["id"] == "github")
    assert github["display_name"] == "GitHub"
    assert github["transport"] == "streamable_http"
    assert github["auth_type"] == "api_key"
    assert github["secret_label"] == "GitHub personal access token"
    assert github["config_fields"] == []
    assert "auth_encrypted" not in response.text


async def test_create_stores_the_secret_encrypted_and_never_returns_it(
    client, auth_headers, test_workspace, encryption_key, service_session
):
    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(),
        headers=auth_headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["auth_scope"] == "workspace"
    assert body["has_auth"] is True
    assert body["tools"] == []
    assert body["last_tested_at"] is None
    assert "auth_encrypted" not in body
    assert "ghp-plain-token" not in response.text

    listed = await client.get(
        f"/api/workspaces/{test_workspace.id}/connectors", headers=auth_headers
    )
    assert listed.json()["total"] == 1
    assert "ghp-plain-token" not in listed.text

    stored = (await service_session.execute(select(ConnectorInstance))).scalar_one()
    assert stored.auth_encrypted is not None
    assert b"ghp-plain-token" not in stored.auth_encrypted


async def test_create_rejects_an_unknown_connector_type(client, auth_headers, test_workspace):
    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(connector_type="no-such-connector"),
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Unknown connector type" in response.json()["detail"]


async def test_create_rejects_an_oauth_entry(client, auth_headers, test_workspace):
    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(connector_type="notion", name="Notion", auth_secret=""),
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "OAuth" in response.json()["detail"]


async def test_create_rejects_a_duplicate_name_in_any_case(client, auth_headers, test_workspace, encryption_key):
    first = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(name="GitHub Main"),
        headers=auth_headers,
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(name="github main"),
        headers=auth_headers,
    )

    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


async def test_create_rejects_a_blank_secret_for_an_api_key_entry(client, auth_headers, test_workspace):
    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(auth_secret=""),
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "personal access token" in response.json()["detail"]


async def test_create_rejects_a_secret_for_an_entry_that_takes_none(client, auth_headers, test_workspace):
    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(
            connector_type="everything",
            name="Test server",
            auth_secret="something",
            config={},
        ),
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "does not take a secret" in response.json()["detail"]


async def test_create_rejects_an_undeclared_config_key(client, auth_headers, test_workspace):
    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(
            connector_type="filesystem",
            name="Scratch",
            auth_secret="",
            config={"path": "/tmp/scratch", "typo": "x"},
        ),
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "typo" in response.json()["detail"]


async def test_create_rejects_a_missing_config_value(client, auth_headers, test_workspace):
    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(connector_type="filesystem", name="Scratch", auth_secret="", config={}),
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "'path'" in response.json()["detail"]


async def test_create_rejects_a_field_the_body_does_not_declare(client, auth_headers, test_workspace):
    """`extra="forbid"`: there is no API surface for a value with one legal value."""
    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json={**_body(), "auth_scope": "per_user"},
        headers=auth_headers,
    )

    assert response.status_code == 422


async def test_a_created_connector_reads_back_pending_and_workspace_scoped(
    client, auth_headers, test_workspace, encryption_key
):
    created = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(),
        headers=auth_headers,
    )
    connector_id = created.json()["id"]

    fetched = await client.get(
        f"/api/workspaces/{test_workspace.id}/connectors/{connector_id}", headers=auth_headers
    )

    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["status"] == "pending"
    assert fetched.json()["auth_scope"] == "workspace"


async def test_the_list_returns_catalog_metadata(client, auth_headers, test_workspace, encryption_key):
    await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(),
        headers=auth_headers,
    )

    listed = await client.get(
        f"/api/workspaces/{test_workspace.id}/connectors", headers=auth_headers
    )

    connector = listed.json()["connectors"][0]
    assert connector["connector_type"] == "github"
    assert connector["display_name"] == "GitHub"
    assert connector["transport"] == "streamable_http"
    assert connector["auth_type"] == "api_key"


async def test_get_is_404_for_an_instance_in_another_workspace(
    client, auth_headers, test_workspace, db_session, test_user, encryption_key
):
    """The lookup is scoped by workspace, not merely by id.

    The second workspace is one the caller *is* a member of, so the 404 comes from the
    connector lookup and not from RBAC refusing the workspace itself.
    """
    from app.models.workspace import Workspace, WorkspaceMember

    created = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(),
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text

    other = Workspace(name="Other Workspace", owner_id=test_user.id)
    db_session.add(other)
    await db_session.commit()
    await db_session.refresh(other)
    db_session.add(WorkspaceMember(workspace_id=other.id, user_id=test_user.id, role="owner"))
    await db_session.commit()

    response = await client.get(
        f"/api/workspaces/{other.id}/connectors/{created.json()['id']}", headers=auth_headers
    )

    assert response.status_code == 404, response.text


async def test_a_viewer_cannot_create(client, viewer_headers, test_workspace):
    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors",
        json=_body(),
        headers=viewer_headers,
    )

    assert response.status_code == 403, response.text


async def test_a_viewer_can_read_the_list(client, viewer_headers, test_workspace):
    response = await client.get(
        f"/api/workspaces/{test_workspace.id}/connectors", headers=viewer_headers
    )

    assert response.status_code == 200, response.text


async def _created(client, workspace_id, headers, **overrides):
    response = await client.post(
        f"/api/workspaces/{workspace_id}/connectors",
        json=_body(**overrides),
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_update_with_a_blank_secret_keeps_the_ciphertext(
    client, auth_headers, test_workspace, encryption_key, service_session
):
    """The established LLM-profile rule: blank means unchanged."""
    created = await _created(client, test_workspace.id, auth_headers)
    before = (
        await service_session.execute(
            select(ConnectorInstance).where(ConnectorInstance.id == created["id"])
        )
    ).scalar_one()
    ciphertext_before = before.auth_encrypted

    response = await client.put(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}",
        json={"name": "GitHub (renamed)", "auth_secret": "", "config": {}},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["has_auth"] is True

    service_session.expire_all()
    after = (
        await service_session.execute(
            select(ConnectorInstance).where(ConnectorInstance.id == created["id"])
        )
    ).scalar_one()
    assert after.auth_encrypted == ciphertext_before


async def test_a_new_secret_replaces_the_ciphertext_and_resets_the_status(
    client, auth_headers, test_workspace, encryption_key, service_session
):
    created = await _created(client, test_workspace.id, auth_headers)

    # Make it look verified, so the reset has something to undo.
    row = (
        await service_session.execute(
            select(ConnectorInstance).where(ConnectorInstance.id == created["id"])
        )
    ).scalar_one()
    row.status = "enabled"
    row.tool_names = ["get_me"]
    row.last_error = None
    await service_session.commit()
    ciphertext_before = row.auth_encrypted

    response = await client.put(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}",
        json={"name": created["name"], "auth_secret": "ghp-a-new-token", "config": {}},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "pending"
    assert response.json()["tools"] == []

    service_session.expire_all()
    after = (
        await service_session.execute(
            select(ConnectorInstance).where(ConnectorInstance.id == created["id"])
        )
    ).scalar_one()
    assert after.auth_encrypted != ciphertext_before


async def test_a_changed_config_resets_the_status_even_with_a_blank_secret(
    client, auth_headers, test_workspace, encryption_key, service_session
):
    created = await _created(
        client,
        test_workspace.id,
        auth_headers,
        connector_type="filesystem",
        name="Scratch",
        auth_secret="",
        config={"path": "/tmp/one"},
    )
    row = (
        await service_session.execute(
            select(ConnectorInstance).where(ConnectorInstance.id == created["id"])
        )
    ).scalar_one()
    row.status = "enabled"
    row.tool_names = ["read_file"]
    await service_session.commit()

    response = await client.put(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}",
        json={"name": "Scratch", "auth_secret": "", "config": {"path": "/tmp/two"}},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "pending"
    assert response.json()["config"] == {"path": "/tmp/two"}


async def test_a_rename_alone_keeps_the_status_and_tools(
    client, auth_headers, test_workspace, encryption_key, service_session
):
    created = await _created(client, test_workspace.id, auth_headers)
    row = (
        await service_session.execute(
            select(ConnectorInstance).where(ConnectorInstance.id == created["id"])
        )
    ).scalar_one()
    row.status = "enabled"
    row.tool_names = ["get_me"]
    row.last_error = None
    await service_session.commit()

    response = await client.put(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}",
        json={"name": "GitHub (renamed)", "auth_secret": "", "config": {}},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "enabled"
    assert response.json()["tools"] == ["get_me"]


async def test_update_rejects_a_duplicate_name(
    client, auth_headers, test_workspace, encryption_key
):
    await _created(client, test_workspace.id, auth_headers, name="Primary")
    second = await _created(client, test_workspace.id, auth_headers, name="Secondary")

    response = await client.put(
        f"/api/workspaces/{test_workspace.id}/connectors/{second['id']}",
        json={"name": "primary", "auth_secret": "", "config": {}},
        headers=auth_headers,
    )

    assert response.status_code == 409, response.text


async def test_update_accepts_an_unchanged_name(
    client, auth_headers, test_workspace, encryption_key
):
    """The uniqueness check must exclude the row being updated, or a rename is impossible."""
    created = await _created(client, test_workspace.id, auth_headers, name="GitHub")

    response = await client.put(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}",
        json={"name": "GitHub", "auth_secret": "", "config": {}},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text


async def test_delete_removes_the_row(client, auth_headers, test_workspace, encryption_key):
    created = await _created(client, test_workspace.id, auth_headers)

    deleted = await client.delete(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}",
        headers=auth_headers,
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"success": True}

    gone = await client.get(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}", headers=auth_headers
    )
    assert gone.status_code == 404


async def test_delete_is_404_for_an_unknown_id(client, auth_headers, test_workspace):
    response = await client.delete(
        f"/api/workspaces/{test_workspace.id}/connectors/no-such-id", headers=auth_headers
    )

    assert response.status_code == 404


async def test_a_viewer_cannot_update_or_delete(
    client, auth_headers, viewer_headers, test_workspace, encryption_key
):
    created = await _created(client, test_workspace.id, auth_headers)

    updated = await client.put(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}",
        json={"name": "Renamed", "auth_secret": "", "config": {}},
        headers=viewer_headers,
    )
    deleted = await client.delete(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}",
        headers=viewer_headers,
    )

    assert updated.status_code == 403, updated.text
    assert deleted.status_code == 403, deleted.text


from pathlib import Path

import app.routers.connectors as connectors_router
from app.services import connector_runtime


def test_the_adapter_is_pinned_in_requirements():
    """Written by the install step, from the version pip actually resolved."""
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text()
    pinned = [
        line.strip()
        for line in requirements.splitlines()
        if line.strip().startswith("langchain-mcp-adapters==")
    ]
    assert len(pinned) == 1, f"expected one exact pin, found {pinned!r}"


async def test_a_successful_probe_records_enabled_and_the_tool_names(
    client, auth_headers, test_workspace, encryption_key, monkeypatch
):
    created = await _created(client, test_workspace.id, auth_headers)

    async def fake_probe(instance):
        return ["get_me", "list_issues"]

    monkeypatch.setattr(connectors_router, "probe_connector_tools", fake_probe)

    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}/test",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "enabled"
    assert body["tools"] == ["get_me", "list_issues"]
    assert body["last_error"] is None
    assert body["last_tested_at"] is not None

    listed = await client.get(
        f"/api/workspaces/{test_workspace.id}/connectors?usable=true", headers=auth_headers
    )
    assert listed.json()["total"] == 1, "an enabled connector is usable"


async def test_a_failed_probe_records_the_error_and_still_returns_200(
    client, auth_headers, test_workspace, encryption_key, monkeypatch
):
    """A server that does not answer is a result to show, not a failed request."""
    created = await _created(client, test_workspace.id, auth_headers)

    async def failing_probe(instance):
        raise connector_runtime.ConnectorProbeError("401 Unauthorized")

    monkeypatch.setattr(connectors_router, "probe_connector_tools", failing_probe)

    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}/test",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "error"
    assert body["last_error"] == "401 Unauthorized"
    assert body["tools"] == []
    assert body["last_tested_at"] is not None

    listed = await client.get(
        f"/api/workspaces/{test_workspace.id}/connectors?usable=true", headers=auth_headers
    )
    assert listed.json()["total"] == 0, "an errored connector is not usable"


async def test_a_failed_probe_clears_a_previous_tool_list(
    client, auth_headers, test_workspace, encryption_key, monkeypatch
):
    """`tools` always describes the most recent probe, so a stale list cannot be read
    next to an error badge as though those tools still work."""
    created = await _created(client, test_workspace.id, auth_headers)

    async def ok_probe(instance):
        return ["get_me"]

    monkeypatch.setattr(connectors_router, "probe_connector_tools", ok_probe)
    await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}/test",
        headers=auth_headers,
    )

    async def failing_probe(instance):
        raise connector_runtime.ConnectorProbeError("Connection refused")

    monkeypatch.setattr(connectors_router, "probe_connector_tools", failing_probe)
    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors/{created['id']}/test",
        headers=auth_headers,
    )

    assert response.json()["tools"] == []


async def test_probe_of_an_unknown_instance_is_404(client, auth_headers, test_workspace):
    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors/no-such-id/test", headers=auth_headers
    )

    assert response.status_code == 404


async def test_probe_of_a_type_that_left_the_catalog_is_400(
    client, auth_headers, test_workspace, encryption_key, service_session
):
    from app.crypto import encrypt_api_key

    instance = ConnectorInstance(
        workspace_id=test_workspace.id,
        connector_type="retired-connector",
        name="Retired",
        status="pending",
        auth_scope="workspace",
        auth_encrypted=encrypt_api_key("whatever"),
        config={},
        tool_names=[],
    )
    service_session.add(instance)
    await service_session.commit()
    await service_session.refresh(instance)

    tested = await client.post(
        f"/api/workspaces/{test_workspace.id}/connectors/{instance.id}/test",
        headers=auth_headers,
    )
    listed = await client.get(
        f"/api/workspaces/{test_workspace.id}/connectors", headers=auth_headers
    )

    assert tested.status_code == 400, tested.text
    assert "Unknown connector type" in tested.json()["detail"]
    assert listed.status_code == 200, "a list must tolerate catalog drift"
    assert listed.json()["connectors"][0]["transport"] == "unknown"


class _StubTool:
    def __init__(self, name: str):
        self.name = name


class _StubClient:
    """Enough of `MultiServerMCPClient` for the loader, without a transport."""

    connections_seen: list[dict] = []
    tools_by_server: dict[str, list[str]] = {}

    def __init__(self, connections, **_kwargs):
        _StubClient.connections_seen.append(connections)

    async def get_tools(self, *, server_name=None):
        return [_StubTool(name) for name in _StubClient.tools_by_server.get(server_name, [])]


async def test_load_connector_tools_builds_the_client_from_the_instances(
    encryption_key, service_session, test_workspace, monkeypatch
):
    from app.crypto import encrypt_api_key

    _StubClient.connections_seen = []
    _StubClient.tools_by_server = {}

    first = ConnectorInstance(
        workspace_id=test_workspace.id,
        connector_type="github",
        name="GitHub",
        status="enabled",
        auth_scope="workspace",
        auth_encrypted=encrypt_api_key("ghp-token"),
        config={},
        tool_names=["get_me"],
    )
    second = ConnectorInstance(
        workspace_id=test_workspace.id,
        connector_type="filesystem",
        name="Files",
        status="pending",
        auth_scope="workspace",
        auth_encrypted=None,
        config={"path": "/tmp/scratch"},
        tool_names=[],
    )
    service_session.add_all([first, second])
    await service_session.commit()
    await service_session.refresh(first)
    await service_session.refresh(second)

    _StubClient.tools_by_server = {first.id: ["get_me"], second.id: ["read_file"]}
    monkeypatch.setattr(connector_runtime, "MultiServerMCPClient", _StubClient)

    tools = await connector_runtime.load_connector_tools([first, second])

    assert [tool.name for tool in tools] == ["get_me", "read_file"]
    assert set(_StubClient.connections_seen[0]) == {first.id, second.id}, "keyed by instance id"
    assert (
        _StubClient.connections_seen[0][first.id]["headers"]["Authorization"]
        == "Bearer ghp-token"
    ), "the loader decrypts, and does not filter by status"


async def test_load_connector_tools_prefixes_a_colliding_name(
    encryption_key, service_session, test_workspace, monkeypatch
):
    from app.crypto import encrypt_api_key

    _StubClient.connections_seen = []
    _StubClient.tools_by_server = {}

    first = ConnectorInstance(
        workspace_id=test_workspace.id,
        connector_type="github",
        name="Main",
        status="enabled",
        auth_scope="workspace",
        auth_encrypted=encrypt_api_key("ghp-token"),
        config={},
        tool_names=[],
    )
    second = ConnectorInstance(
        workspace_id=test_workspace.id,
        connector_type="github",
        name="Other",
        status="enabled",
        auth_scope="workspace",
        auth_encrypted=encrypt_api_key("ghp-other"),
        config={},
        tool_names=[],
    )
    service_session.add_all([first, second])
    await service_session.commit()
    await service_session.refresh(first)
    await service_session.refresh(second)

    _StubClient.tools_by_server = {first.id: ["search"], second.id: ["search"]}
    monkeypatch.setattr(connector_runtime, "MultiServerMCPClient", _StubClient)

    tools = await connector_runtime.load_connector_tools([first, second])

    assert sorted(tool.name for tool in tools) == ["main_search", "other_search"]


async def test_load_connector_tools_returns_nothing_without_instances(monkeypatch):
    monkeypatch.setattr(
        connector_runtime,
        "MultiServerMCPClient",
        lambda *args, **kwargs: pytest.fail("no client should be built with nothing to load"),
    )

    assert await connector_runtime.load_connector_tools([]) == []
