"""MongoDB executor for external data sources (addendum 2026-11-05).

`find` only: the model gets one collection at a time, filtered by a JSON
document the mongo guard has already vetted (allowlist + code-execution
operator denylist). PyMongo is sync and runs via `asyncio.to_thread`; one
client per call, closed after. Limits mirror the SQL executors: 200 rows,
256 KB payload, 10s server-side max_time_ms, 12s client backstop.

`describe()` samples up to five documents per collection for top-level field
names and BSON types — the picker needs names; the shape hints help the model.
"""

import asyncio
import json
import time
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlsplit

import pymongo
from bson import Decimal128, ObjectId

from app.logging import logger

from .mongo_guard import validate_find
from .types import Column, QueryResult, Table

ROW_LIMIT = 200
RESPONSE_CAP_BYTES = 256 * 1024
STATEMENT_TIMEOUT_MS = 10_000
CLIENT_BACKSTOP_S = 12
CONNECT_TIMEOUT_MS = 5_000
DESCRIBE_BACKSTOP_S = 6
MAX_COLLECTIONS = 500
MAX_COLUMNS_PER_TABLE = 200
SAMPLE_DOCUMENTS = 5

BSON_TYPE_NAMES = {
    "str": "string",
    "int": "int",
    "float": "double",
    "bool": "bool",
    "datetime": "date",
    "list": "array",
    "dict": "object",
    "bytes": "binData",
    "ObjectId": "objectId",
    "Decimal128": "decimal",
    "type(None)": "null",
}


class DataSourceError(Exception):
    """A find or describe failed. The message is safe to show to the model."""


def _default_database(uri: str) -> str:
    return urlsplit(uri).path.lstrip("/").split("?")[0]


def _to_json_value(value: object) -> object:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, Decimal128):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_to_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_json_value(item) for key, item in value.items()}
    return str(value)


def _sanitize(message: str, uri: str) -> str:
    cleaned = message.replace(uri, "<uri>")
    if "://" in cleaned:
        cleaned = cleaned.split("://", 1)[0] + "<uri>"
    return cleaned


def _client(uri: str) -> pymongo.MongoClient:
    return pymongo.MongoClient(
        uri,
        serverSelectionTimeoutMS=CONNECT_TIMEOUT_MS,
        connectTimeoutMS=CONNECT_TIMEOUT_MS,
        socketTimeoutMS=int(CLIENT_BACKSTOP_S * 1000),
        appname="mokinjay-data-source",
    )


def _find_sync(
    uri: str,
    database: str,
    collection: str,
    filter_doc: dict,
    projection_doc: dict | None,
    limit: int,
) -> list[dict]:
    try:
        client = _client(uri)
    except Exception as exc:
        raise DataSourceError(_sanitize(str(exc), uri)) from exc
    try:
        cursor = client[database][collection].find(
            filter_doc,
            projection_doc,
            limit=limit,
            max_time_ms=STATEMENT_TIMEOUT_MS,
        )
        return list(cursor)
    except pymongo.errors.PyMongoError as exc:
        raise DataSourceError(_sanitize(str(exc), uri)) from exc
    finally:
        client.close()


async def run_find(
    uri: str,
    database: str,
    collection: str,
    allowed_collections: list[str],
    filter_json: str,
    projection_json: str | None = None,
    limit: int | None = None,
    *,
    agent_id: str | None = None,
    connection_id: str | None = None,
    client_backstop_s: float = CLIENT_BACKSTOP_S,
) -> QueryResult:
    """Validate and run one read-only find against MongoDB; bounded result."""
    filter_doc, projection_doc, capped_limit = validate_find(
        collection, filter_json, projection_json, allowed_collections, limit
    )
    started = time.monotonic()

    try:
        documents = await asyncio.wait_for(
            asyncio.to_thread(
                _find_sync,
                uri,
                database,
                collection,
                filter_doc,
                projection_doc,
                capped_limit + 1,
            ),
            timeout=client_backstop_s,
        )
    except asyncio.TimeoutError as exc:
        raise DataSourceError(
            f"the query timed out after {client_backstop_s:g}s (client backstop)"
        ) from exc

    more = len(documents) > capped_limit
    documents = documents[:capped_limit]

    # Mongo documents are shaped per row; the payload is the documents
    # themselves plus the union of top-level field names.
    field_names: list[str] = []
    seen: set[str] = set()
    rows_out: list[list[object]] = []
    size = 2
    truncated = more
    for document in documents:
        for key in document:
            if key not in seen:
                seen.add(key)
                field_names.append(key)
        values = [_to_json_value(document.get(name)) for name in field_names]
        chunk = len(json.dumps(values, default=str))
        if size + chunk > RESPONSE_CAP_BYTES:
            truncated = True
            break
        rows_out.append(values)
        size += chunk + 1

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        f"data source query: connection={connection_id} agent={agent_id} "
        f"duration_ms={duration_ms} rows={len(rows_out)} truncated={truncated} "
        f"collection={collection!r}"
    )
    return QueryResult(
        columns=field_names,
        rows=rows_out,
        row_count=len(rows_out),
        truncated=truncated,
        duration_ms=duration_ms,
    )


def _describe_sync(uri: str, database: str) -> dict[str, list[dict]]:
    try:
        client = _client(uri)
    except Exception as exc:
        raise DataSourceError(_sanitize(str(exc), uri)) from exc
    try:
        db = client[database]
        names = db.list_collection_names()
        sampled: dict[str, list[dict]] = {}
        for name in names[:MAX_COLLECTIONS]:
            try:
                documents = list(db[name].find({}, limit=SAMPLE_DOCUMENTS))
            except pymongo.errors.PyMongoError:
                documents = []
            sampled[name] = documents
        return sampled
    except pymongo.errors.PyMongoError as exc:
        raise DataSourceError(_sanitize(str(exc), uri)) from exc
    finally:
        client.close()


async def describe(
    uri: str,
    *,
    database: str | None = None,
    max_tables: int = MAX_COLLECTIONS,
    max_columns: int = MAX_COLUMNS_PER_TABLE,
) -> list[Table]:
    """Collection list with sampled top-level fields (addendum 2026-11-05)."""
    started = time.monotonic()
    database = database or _default_database(uri)
    if not database:
        raise DataSourceError(
            "the connection has no database: set database_name on the connection record"
        )

    try:
        sampled = await asyncio.wait_for(
            asyncio.to_thread(_describe_sync, uri, database),
            timeout=DESCRIBE_BACKSTOP_S,
        )
    except asyncio.TimeoutError as exc:
        raise DataSourceError(
            f"schema introspection timed out after {DESCRIBE_BACKSTOP_S:g}s"
        ) from exc

    tables: list[Table] = []
    for name in sorted(sampled):
        columns: list[Column] = []
        seen: set[str] = set()
        for document in sampled[name]:
            for key, value in document.items():
                if key in seen or len(columns) >= max_columns:
                    continue
                seen.add(key)
                columns.append(
                    Column(
                        name=key,
                        type=BSON_TYPE_NAMES.get(type(value).__name__, "mixed"),
                        nullable=True,
                    )
                )
        tables.append(Table(schema=database, name=name, columns=columns))

    duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(f"data source describe: collections={len(tables)} duration_ms={duration_ms}")
    return tables


__all__ = ["DataSourceError", "describe", "run_find"]
