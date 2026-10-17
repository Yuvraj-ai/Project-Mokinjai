"""The predefined connector catalog.

A connector is a kind of MCP server, not a thing a user authors (ADR-013). Every
piece of per-server knowledge — the endpoint, the transport, which auth header it
wants, which values it needs — lives here and nowhere else, the way
`engine/modules/registry.py` keeps its node types in plain Python rather than in a
table. `args` entries are `str.format` templates whose namespace is the instance's
`config` keys plus `secret`; a template naming a value nobody supplies raises rather
than launching a server with a literal `{path}` argument.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    display_name: str
    description: str
    transport: str
    auth_type: str
    url: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()
    auth_header: str | None = None
    auth_prefix: str = ""
    secret_label: str | None = None
    config_fields: tuple[str, ...] = ()
    docs_url: str | None = None


ENTRIES: tuple[CatalogEntry, ...] = (
    CatalogEntry(
        id="github",
        display_name="GitHub",
        description="Repositories, issues, pull requests and code search on GitHub.",
        transport="streamable_http",
        auth_type="api_key",
        url="https://api.githubcopilot.com/mcp/",
        auth_header="Authorization",
        auth_prefix="Bearer ",
        secret_label="GitHub personal access token",
        docs_url="https://github.com/github/github-mcp-server",
    ),
    CatalogEntry(
        id="postgres",
        display_name="PostgreSQL",
        description="Read-only schema inspection and queries against a PostgreSQL database.",
        transport="stdio",
        auth_type="connection_string",
        command="npx",
        args=("-y", "@modelcontextprotocol/server-postgres", "{secret}"),
        secret_label="PostgreSQL connection URI",
        config_fields=("database",),
    ),
    CatalogEntry(
        id="filesystem",
        display_name="Filesystem",
        description="Read and write files inside one directory on the Mokinjay host.",
        transport="stdio",
        auth_type="none",
        command="npx",
        args=("-y", "@modelcontextprotocol/server-filesystem", "{path}"),
        config_fields=("path",),
    ),
    CatalogEntry(
        id="everything",
        display_name="Everything (test server)",
        description=(
            "The MCP reference server. Advertises tools, prompts and resources; "
            "used to check connectivity without a credential."
        ),
        transport="stdio",
        auth_type="none",
        command="npx",
        args=("-y", "@modelcontextprotocol/server-everything"),
    ),
    CatalogEntry(
        id="slack",
        display_name="Slack",
        description="Search and read Slack channels, threads and files.",
        transport="streamable_http",
        auth_type="oauth",
        url="https://mcp.slack.com/mcp",
        docs_url="https://docs.slack.dev/ai/slack-mcp-server/",
    ),
    CatalogEntry(
        id="notion",
        display_name="Notion",
        description="Search and read pages and databases in a Notion workspace.",
        transport="streamable_http",
        auth_type="oauth",
        url="https://mcp.notion.com/mcp",
        docs_url="https://developers.notion.com/guides/mcp",
    ),
)

_CATALOG: dict[str, CatalogEntry] = {entry.id: entry for entry in ENTRIES}


def get_entry(connector_type: str) -> CatalogEntry | None:
    """The entry for a stored `connector_type`, or None if the catalog no longer has it."""
    return _CATALOG.get(connector_type)


def list_entries() -> list[CatalogEntry]:
    return list(ENTRIES)
