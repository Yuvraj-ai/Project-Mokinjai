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
