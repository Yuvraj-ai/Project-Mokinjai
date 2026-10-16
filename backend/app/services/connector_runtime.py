"""Turn a stored connector instance into an MCP server connection.

`server_config` is pure and is the only place a `langchain-mcp-adapters` connection
dict is produced, which is why the shape is tested here rather than at the network
edge. `connection_for` adds the one piece of state a pure function cannot reach: the
decryption of the instance's stored secret.
"""

from collections.abc import Sequence
from typing import Any

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
    secret = (
        decrypt_api_key(instance.auth_encrypted)
        if instance.auth_encrypted is not None
        else None
    )
    return server_config(entry, secret, dict(instance.config or {}))


def connections_for(instances: Sequence[ConnectorInstance]) -> dict[str, dict[str, Any]]:
    """Connection dicts keyed by instance id — unique, stable, and free of user text."""
    return {instance.id: connection_for(instance) for instance in instances}
