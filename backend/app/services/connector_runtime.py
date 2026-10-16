"""Turn a stored connector instance into an MCP server connection.

`server_config` is pure and is the only place a `langchain-mcp-adapters` connection
dict is produced, which is why the shape is tested here rather than at the network
edge. `connection_for` adds the one piece of state a pure function cannot reach: the
decryption of the instance's stored secret.
"""

import asyncio
from collections import Counter
from collections.abc import Sequence
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.crypto import decrypt_api_key
from app.models.connector import ConnectorInstance
from app.services.connector_catalog import CatalogEntry, get_entry


class ConnectorProbeError(Exception):
    """A connector could not be turned into a usable connection, or did not answer."""


def slug(name: str) -> str:
    """A tool-name-safe form of an instance name, used when two tools collide."""
    collapsed = "".join(
        character.lower() if character.isalnum() else "_" for character in name.strip()
    )
    while "__" in collapsed:
        collapsed = collapsed.replace("__", "_")
    return collapsed.strip("_") or "connector"


def server_config(
    entry: CatalogEntry, secret: str | None, config: dict[str, Any]
) -> dict[str, Any]:
    """The connection dict for one catalog entry, given its already-resolved values."""
    if entry.transport == "stdio":
        if not entry.command:
            raise ConnectorProbeError(f"{entry.display_name} declares no command")
        values = {**config, "secret": secret or ""}
        args: list[str] = []
        for template in entry.args:
            try:
                args.append(template.format(**values))
            except KeyError as exc:
                raise ConnectorProbeError(
                    f"{entry.display_name} needs {exc.args[0]!r} in its configuration"
                ) from exc
            except (IndexError, ValueError) as exc:
                raise ConnectorProbeError(
                    f"{entry.display_name} has a malformed argument template {template!r}"
                ) from exc
        return {"transport": "stdio", "command": entry.command, "args": args}

    if entry.transport == "streamable_http":
        if not entry.url:
            raise ConnectorProbeError(f"{entry.display_name} declares no URL")
        headers: dict[str, str] = {}
        if entry.auth_type == "api_key":
            if not secret:
                raise ConnectorProbeError(
                    f"{entry.secret_label or 'A secret'} is required for {entry.display_name}"
                )
            if not entry.auth_header:
                raise ConnectorProbeError(f"{entry.display_name} declares no auth header")
            headers[entry.auth_header] = f"{entry.auth_prefix}{secret}"
        return {"transport": "streamable_http", "url": entry.url, "headers": headers}

    raise ConnectorProbeError(
        f"{entry.display_name} uses an unsupported transport {entry.transport!r}"
    )


def connection_for(instance: ConnectorInstance) -> dict[str, Any]:
    """The connection dict for a stored instance, decrypting its secret.

    A `connector_type` the catalog no longer has raises rather than being skipped: the
    agent that names this connector names a capability the deployment can no longer
    resolve, and a loud failure is better than a silently missing tool.
    """
    entry = get_entry(instance.connector_type)
    if entry is None:
        raise ConnectorProbeError(
            f"{instance.connector_type!r} is no longer in the connector catalog; "
            "restore the catalog entry or delete this connector"
        )
    try:
        secret = (
            decrypt_api_key(instance.auth_encrypted)
            if instance.auth_encrypted is not None
            else None
        )
    except Exception as exc:
        raise ConnectorProbeError(
            "Stored credentials could not be decrypted (encryption key mismatch or corrupted secret)"
        ) from exc
    return server_config(entry, secret, dict(instance.config or {}))


def connections_for(instances: Sequence[ConnectorInstance]) -> dict[str, dict[str, Any]]:
    """Connection dicts keyed by instance id — unique, stable, and free of user text."""
    return {instance.id: connection_for(instance) for instance in instances}


_PROBE_TIMEOUT_SECONDS = 30.0
_TRUNCATED_LENGTH = 500


def _short(exc: BaseException) -> str:
    """The failure text as `llm_probe` produces it: one line, bounded, never empty."""
    text = str(exc).strip().replace("\n", " ") or exc.__class__.__name__
    return text if len(text) <= _TRUNCATED_LENGTH else text[:_TRUNCATED_LENGTH] + "…"


async def _list_tool_names(connection: dict[str, Any], *, server_name: str) -> list[str]:
    client = MultiServerMCPClient({server_name: connection})
    try:
        tools = await asyncio.wait_for(
            client.get_tools(server_name=server_name), timeout=_PROBE_TIMEOUT_SECONDS
        )
    except TimeoutError as exc:
        raise ConnectorProbeError(
            f"the server did not answer within {_PROBE_TIMEOUT_SECONDS:.0f}s"
        ) from exc
    except Exception as exc:
        # Every transport failure reads the same to a user: the server did not answer,
        # and here is what it said. The connection dict is deliberately not logged.
        raise ConnectorProbeError(_short(exc)) from exc
    return sorted(tool.name for tool in tools)


async def probe_connector_tools(instance: ConnectorInstance) -> list[str]:
    """Ask one connector which tools it exposes. The test action calls this.

    Imported into `app.routers.connectors` so tests can replace it there, exactly as
    `test_llm_profiles.py` replaces `probe_llm`.
    """
    return await _list_tool_names(connection_for(instance), server_name=instance.id)


async def load_connector_tools(instances: Sequence[ConnectorInstance]) -> list[BaseTool]:
    """Every tool the given connectors expose, as LangChain tools.

    This is Phase 3's entry point. It does not filter by `status`: an agent's assignment
    is the authority (ADR-009/ADR-016) and a connector that failed its last probe may be
    reachable now. Tools are collected per instance rather than in one call so a name
    collision can be attributed; when two servers expose the same name, both are prefixed
    with their owning instance's slug. Renaming is safe because the adapter opens the
    session at invocation time from the stored connection, not from the tool's name.
    """
    if not instances:
        return []
    client = MultiServerMCPClient(connections_for(instances))

    loaded: list[tuple[str, BaseTool]] = []
    for instance in instances:
        for tool in await client.get_tools(server_name=instance.id):
            loaded.append((instance.name, tool))

    collisions = Counter(tool.name for _, tool in loaded)
    for owner, tool in loaded:
        if collisions[tool.name] > 1:
            tool.name = f"{slug(owner)}_{tool.name}"
    return [tool for _, tool in loaded]
