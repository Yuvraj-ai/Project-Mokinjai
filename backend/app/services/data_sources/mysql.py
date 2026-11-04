"""MySQL executor for external data sources (addendum 2026-11-05).

Same contract as the Postgres executor: guard, driver-API read-only
transaction, bounded payload, one connection per call. PyMySQL is sync and
runs off the request path via `asyncio.to_thread` — the runtime's single
blocking hop, as the sandbox documents.

MySQL has no schemas (the database is the schema), so a `describe()` returns
the connection's database as every table's schema — matching how the
allowlist snapshot qualifies names (`db.table`).
"""

import asyncio
import json
import time
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlsplit

import pymysql

from app.logging import logger

from .guard import validate
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

# MySQL's error code for "killed by MAX_EXECUTION_TIME".
_ER_MAX_EXECUTION_TIME = 3024


class DataSourceError(Exception):
    """A query or describe failed. The message is safe to show to the model."""


def _to_json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _sanitize(message: str, uri: str) -> str:
    cleaned = message.replace(uri, "<uri>")
    if "://" in cleaned:
        cleaned = cleaned.split("://", 1)[0] + "<uri>"
    return cleaned


def _connect(uri: str):
    parts = urlsplit(uri)
    return pymysql.connect(
        host=parts.hostname or "localhost",
        port=parts.port or 3306,
        user=parts.username or "",
        password=parts.password or "",
        database=parts.path.lstrip("/") or None,
        connect_timeout=CONNECT_TIMEOUT_S,
        read_timeout=int(CLIENT_BACKSTOP_S),
        write_timeout=CONNECT_TIMEOUT_S,
        charset="utf8mb4",
    )


def _connection_failed(exc: Exception) -> DataSourceError:
    logger.warning(f"data source connection failed: {type(exc).__name__}")
    return DataSourceError(
        "could not connect to the external database (check the host, port and credentials)"
    )


def _query_sync(uri: str, sql: str, statement_timeout_ms: int) -> tuple[list[str], list[tuple]]:
    """The blocking body: connect, read-only transaction, fetch. Thread-only."""
    try:
        conn = _connect(uri)
    except Exception as exc:  # OperationalError, OSError, ...
        raise _connection_failed(exc) from exc
    try:
        with conn.cursor() as cursor:
            # MAX_EXECUTION_TIME is SELECT-only and takes a bare integer; the
            # guard above guarantees both, so inlining the value is safe.
            cursor.execute(f"SET SESSION MAX_EXECUTION_TIME = {int(statement_timeout_ms)}")
            cursor.execute("START TRANSACTION READ ONLY")
            cursor.execute(sql)
            rows = cursor.fetchmany(ROW_LIMIT + 1)
            columns = [col[0] for col in (cursor.description or [])]
        conn.rollback()
    except pymysql.err.OperationalError as exc:
        code = exc.args[0] if exc.args else None
        if code == _ER_MAX_EXECUTION_TIME:
            raise DataSourceError(
                f"the query timed out after {statement_timeout_ms / 1000:g}s"
            ) from exc
        raise DataSourceError(_sanitize(str(exc), uri)) from exc
    except pymysql.MySQLError as exc:
        raise DataSourceError(_sanitize(str(exc), uri)) from exc
    finally:
        conn.close()
    return columns, rows


async def run(
    uri: str,
    sql: str,
    allowed_tables: list[str],
    *,
    agent_id: str | None = None,
    connection_id: str | None = None,
    dialect: str = "mysql",
    statement_timeout_ms: int = STATEMENT_TIMEOUT_MS,
    client_backstop_s: float = CLIENT_BACKSTOP_S,
) -> QueryResult:
    """Validate and run one read-only SELECT against MySQL; bounded result."""
    validate(sql, dialect, allowed_tables)
    started = time.monotonic()

    try:
        columns, raw_rows = await asyncio.wait_for(
            asyncio.to_thread(_query_sync, uri, sql, statement_timeout_ms),
            timeout=client_backstop_s,
        )
    except asyncio.TimeoutError as exc:
        raise DataSourceError(
            f"the query timed out after {client_backstop_s:g}s (client backstop)"
        ) from exc

    more_rows = len(raw_rows) > ROW_LIMIT
    raw_rows = raw_rows[:ROW_LIMIT]

    rows_out: list[list[object]] = []
    size = 2
    truncated = more_rows
    for row in raw_rows:
        values = [_to_json_value(value) for value in row]
        chunk = len(json.dumps(values, default=str))
        if size + chunk > RESPONSE_CAP_BYTES:
            truncated = True
            break
        rows_out.append(values)
        size += chunk + 1

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        f"data source query: connection={connection_id} agent={agent_id} "
        f"duration_ms={duration_ms} rows={len(rows_out)} truncated={truncated} sql={sql!r}"
    )
    return QueryResult(
        columns=columns,
        rows=rows_out,
        row_count=len(rows_out),
        truncated=truncated,
        duration_ms=duration_ms,
    )


def _describe_sync(uri: str) -> list[tuple]:
    try:
        conn = _connect(uri)
    except Exception as exc:  # OperationalError, OSError, ...
        raise _connection_failed(exc) from exc
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT table_schema, table_name, column_name, data_type, is_nullable "
                "FROM information_schema.columns WHERE table_schema = DATABASE() "
                "ORDER BY table_name, ordinal_position"
            )
            rows = cursor.fetchall()
        conn.rollback()
    except pymysql.MySQLError as exc:
        raise DataSourceError(_sanitize(str(exc), uri)) from exc
    finally:
        conn.close()
    return rows


async def describe(
    uri: str,
    *,
    max_tables: int = MAX_TABLES,
    max_columns: int = MAX_COLUMNS_PER_TABLE,
) -> list[Table]:
    """Introspect the connection's database for the picker and describe tool."""
    started = time.monotonic()
    try:
        rows = await asyncio.wait_for(
            asyncio.to_thread(_describe_sync, uri),
            timeout=DESCRIBE_BACKSTOP_S,
        )
    except asyncio.TimeoutError as exc:
        raise DataSourceError(
            f"schema introspection timed out after {DESCRIBE_BACKSTOP_S:g}s"
        ) from exc

    tables: list[Table] = []
    index: dict[str, int] = {}
    # The database IS the schema in MySQL; qualifying with the real database
    # name keeps describe() consistent with `db.table` allowlist entries.
    database = urlsplit(uri).path.lstrip("/") or ""
    for _schema, table_name, column_name, data_type, is_nullable in rows:
        position = index.get(table_name)
        if position is None:
            if len(tables) >= max_tables:
                break
            position = len(tables)
            index[table_name] = position
            tables.append(Table(schema=database, name=table_name, columns=[]))
        if len(tables[position].columns) < max_columns:
            tables[position].columns.append(
                Column(name=column_name, type=data_type, nullable=is_nullable == "YES")
            )

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(f"data source describe: tables={len(tables)} duration_ms={duration_ms}")
    return tables


__all__ = ["DataSourceError", "describe", "run"]
