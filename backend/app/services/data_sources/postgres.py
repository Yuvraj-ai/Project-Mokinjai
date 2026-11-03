"""PostgreSQL executor for external data sources (spec §2.4, §2.5).

In-process, host-side (D2): the Docker sandbox never sees a URI. Every query
passes the SQL guard, runs inside a driver-API read-only transaction under a
server-side `statement_timeout`, and returns a bounded payload. One connection
per call, closed in `finally` — no pooling in v1.

shortcut: no LIMIT rewrite — a huge scan can still run until the timeout before
the first rows arrive.
shortcut: the full SQL text is audited, so literals (possible PII) land in the
log. Hash it if logs become shared.
"""

import asyncio
import json
import time
from datetime import date, datetime
from decimal import Decimal

import asyncpg

from app.logging import logger

from .guard import GuardError, validate
from .types import Column, QueryResult, Table

ROW_LIMIT = 200
RESPONSE_CAP_BYTES = 256 * 1024
STATEMENT_TIMEOUT_MS = 10_000
CLIENT_BACKSTOP_S = 12
CONNECT_TIMEOUT_S = 5
DESCRIBE_STATEMENT_TIMEOUT_MS = 5_000
DESCRIBE_BACKSTOP_S = 6
MAX_TABLES = 500
MAX_COLUMNS_PER_TABLE = 200

_APPLICATION_NAME = "mokinjay-data-source"


class DataSourceError(Exception):
    """A query or describe failed. The message is safe to show to the model."""


def _to_json_value(value: object) -> object:
    """Coerce driver types into JSON-native values (spec §2.4)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _sanitize(message: str, uri: str) -> str:
    """Driver errors must never carry the DSN."""
    cleaned = message.replace(uri, "<uri>")
    # Userinfo or host fragments can survive inside some driver messages.
    if "://" in cleaned:
        cleaned = cleaned.split("://", 1)[0] + "<uri>"
    return cleaned


def _connection_failed(exc: Exception, uri: str) -> DataSourceError:
    logger.warning(f"data source connection failed: {type(exc).__name__}")
    return DataSourceError(
        "could not connect to the external database (check the host, port and credentials)"
    )


async def run(
    uri: str,
    sql: str,
    allowed_tables: list[str],
    *,
    agent_id: str | None = None,
    connection_id: str | None = None,
    dialect: str = "postgres",
    statement_timeout_ms: int = STATEMENT_TIMEOUT_MS,
    client_backstop_s: float = CLIENT_BACKSTOP_S,
) -> QueryResult:
    """Validate and run one read-only SELECT; return a bounded result.

    `statement_timeout_ms` is a parameter only so tests can exercise the cancel
    path in seconds; production always uses the 10 s default.
    """
    validate(sql, dialect, allowed_tables)

    started = time.monotonic()

    async def _execute() -> list[asyncpg.Record]:
        try:
            conn = await asyncpg.connect(
                uri,
                timeout=CONNECT_TIMEOUT_S,
                server_settings={"application_name": _APPLICATION_NAME},
            )
        except Exception as exc:  # OSError, asyncpg.InvalidPasswordError, ...
            raise _connection_failed(exc, uri) from exc
        try:
            async with conn.transaction(readonly=True):  # BEGIN ... READ ONLY
                await conn.execute(
                    "SELECT set_config('statement_timeout', $1, true)",
                    str(statement_timeout_ms),
                )
                cursor = await conn.cursor(sql)  # server-side portal
                return await cursor.fetch(ROW_LIMIT + 1)
        except asyncpg.QueryCanceledError:
            # The server-side statement_timeout fired; the outer handler turns
            # this into the model-facing "timed out" message.
            raise
        except asyncpg.PostgresError as exc:
            raise DataSourceError(_sanitize(str(exc), uri)) from exc
        finally:
            await conn.close()

    try:
        records = await asyncio.wait_for(_execute(), timeout=client_backstop_s)
    except asyncio.TimeoutError as exc:
        raise DataSourceError(
            f"the query timed out after {client_backstop_s:g}s (client backstop)"
        ) from exc
    except asyncpg.PostgresError as exc:
        if isinstance(exc, asyncpg.QueryCanceledError):
            raise DataSourceError(
                f"the query timed out after {statement_timeout_ms / 1000:g}s"
            ) from exc
        raise DataSourceError(_sanitize(str(exc), uri)) from exc

    more_rows = len(records) > ROW_LIMIT
    records = records[:ROW_LIMIT]

    columns = list(records[0].keys()) if records else []
    rows: list[list[object]] = []
    size = 2  # the surrounding "[]"
    over_size = False
    for record in records:
        row = [_to_json_value(value) for value in record]
        chunk = len(json.dumps(row, default=str))
        if size + chunk > RESPONSE_CAP_BYTES:
            over_size = True
            break
        rows.append(row)
        size += chunk + 1

    duration_ms = int((time.monotonic() - started) * 1000)
    truncated = more_rows or over_size

    # Audit (D3, layer 5). The connection id only — never the URI.
    logger.info(
        f"data source query: connection={connection_id} agent={agent_id} "
        f"duration_ms={duration_ms} rows={len(rows)} truncated={truncated} sql={sql!r}"
    )

    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        duration_ms=duration_ms,
    )


async def describe(
    uri: str,
    *,
    max_tables: int = MAX_TABLES,
    max_columns: int = MAX_COLUMNS_PER_TABLE,
) -> list[Table]:
    """Introspect the database for the table picker and describe tool (D6)."""
    started = time.monotonic()

    async def _describe() -> list[Table]:
        try:
            conn = await asyncpg.connect(
                uri,
                timeout=CONNECT_TIMEOUT_S,
                server_settings={"application_name": _APPLICATION_NAME},
            )
        except Exception as exc:  # OSError, asyncpg.InvalidPasswordError, ...
            raise _connection_failed(exc, uri) from exc
        try:
            async with conn.transaction(readonly=True):
                await conn.execute(
                    "SELECT set_config('statement_timeout', $1, true)",
                    str(DESCRIBE_STATEMENT_TIMEOUT_MS),
                )
                rows = await conn.fetch(
                    """
                    select table_schema, table_name, column_name, data_type, is_nullable
                    from information_schema.columns
                    where table_schema not in ('pg_catalog', 'information_schema')
                    order by table_schema, table_name, ordinal_position
                    """
                )
        except asyncpg.PostgresError as exc:
            raise DataSourceError(_sanitize(str(exc), uri)) from exc
        finally:
            await conn.close()
        return rows  # type: ignore[return-value]

    try:
        rows = await asyncio.wait_for(_describe(), timeout=DESCRIBE_BACKSTOP_S)
    except asyncio.TimeoutError as exc:
        raise DataSourceError(
            f"schema introspection timed out after {DESCRIBE_BACKSTOP_S:g}s"
        ) from exc

    tables: list[Table] = []
    index: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (row["table_schema"], row["table_name"])
        position = index.get(key)
        if position is None:
            if len(tables) >= max_tables:
                break
            position = len(tables)
            index[key] = position
            tables.append(Table(schema=key[0], name=key[1], columns=[]))
        if len(tables[position].columns) < max_columns:
            tables[position].columns.append(
                Column(
                    name=row["column_name"],
                    type=row["data_type"],
                    nullable=row["is_nullable"] == "YES",
                )
            )

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        f"data source describe: tables={len(tables)} duration_ms={duration_ms}"
    )
    return tables


__all__ = [
    "DataSourceError",
    "GuardError",
    "ROW_LIMIT",
    "RESPONSE_CAP_BYTES",
    "STATEMENT_TIMEOUT_MS",
    "describe",
    "run",
]
