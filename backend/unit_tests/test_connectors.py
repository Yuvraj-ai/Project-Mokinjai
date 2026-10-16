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


