"""Integration tests for the Postgres executor (spec §2.6).

These run against the local test Postgres from conftest (`mokinjay_test`), the
same server the suite already owns. Each test creates and drops its own table.
"""

import os
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from dotenv import load_dotenv

from app.services.data_sources.guard import GuardError
from app.services.data_sources.postgres import (
    RESPONSE_CAP_BYTES,
    ROW_LIMIT,
    DataSourceError,
    describe,
    run,
)

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://imyuvi@localhost:5432/mokinjay_test"
)
# asyncpg wants the plain URL, not the SQLAlchemy dialect-qualified one.
URI = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

TABLE = "ds_integration_test"
SELECTED = [f"public.{TABLE}"]


@pytest_asyncio.fixture
async def table():
    conn = await asyncpg.connect(URI)
    try:
        await conn.execute(
            f'DROP TABLE IF EXISTS "{TABLE}"'  # noqa: S608 - fixed test table name
        )
        await conn.execute(
            f'CREATE TABLE "{TABLE}" (id int primary key, name text, payload bytea)'
        )
        await conn.executemany(
            f'INSERT INTO "{TABLE}" (id, name) VALUES ($1, $2)',
            [(1, "alpha"), (2, "beta"), (3, "gamma")],
        )
        yield
        await conn.execute(f'DROP TABLE "{TABLE}"')
    finally:
        await conn.close()


class TestRun:
    async def test_returns_rows_and_columns(self, table):
        result = await run(URI, f"SELECT id, name FROM {TABLE} ORDER BY id", SELECTED)

        assert result.columns == ["id", "name"]
        assert result.rows == [[1, "alpha"], [2, "beta"], [3, "gamma"]]
        assert result.row_count == 3
        assert result.truncated is False
        assert result.duration_ms >= 0

    async def test_write_is_refused_and_never_reaches_the_database(self, table):
        with pytest.raises(GuardError):
            await run(URI, f"DELETE FROM {TABLE}", SELECTED)

        conn = await asyncpg.connect(URI)
        count = await conn.fetchval(f'SELECT count(*) FROM "{TABLE}"')
        await conn.close()
        assert count == 3, "the guard, not the database, must be the boundary"

    async def test_multiple_statements_refused(self, table):
        with pytest.raises(GuardError):
            await run(URI, f"SELECT 1; DELETE FROM {TABLE}", SELECTED)

    async def test_row_cap_truncates_at_200(self, table):
        conn = await asyncpg.connect(URI)
        await conn.execute(
            f'INSERT INTO "{TABLE}" (id, name) '
            "SELECT i, 'bulk' FROM generate_series(10, 300) AS i"
        )
        await conn.close()

        result = await run(URI, f"SELECT id FROM {TABLE}", SELECTED)

        assert result.row_count == ROW_LIMIT
        assert result.truncated is True

    async def test_response_cap_stops_before_the_limit(self, table):
        # One megabyte text value: even a single row exceeds the 256 KB payload cap.
        conn = await asyncpg.connect(URI)
        await conn.execute(f'INSERT INTO "{TABLE}" (id, name) VALUES (99, repeat($1, 1000000))', "a")
        await conn.close()

        result = await run(
            URI, f"SELECT name FROM {TABLE} WHERE id = 99", SELECTED
        )

        assert len(result.rows) * RESPONSE_CAP_BYTES <= RESPONSE_CAP_BYTES
        assert result.truncated is True

    async def test_bytes_never_dump_their_content(self, table):
        conn = await asyncpg.connect(URI)
        await conn.execute(f'INSERT INTO "{TABLE}" (id, payload) VALUES (50, $1)', b"secret-bytes")
        await conn.close()

        result = await run(URI, f"SELECT payload FROM {TABLE} WHERE id = 50", SELECTED)

        assert result.rows == [["<12 bytes>"]]

    async def test_statement_timeout_cancels_the_query(self, table):
        with pytest.raises(DataSourceError, match="timed out"):
            await run(
                URI,
                "SELECT pg_sleep(3)",
                SELECTED,
                statement_timeout_ms=500,
            )

    async def test_query_error_is_surfaced(self, table):
        # A column the table does not have passes the guard (the table itself is
        # selected) and fails at the database — the model sees the driver error.
        with pytest.raises(DataSourceError, match="does not exist"):
            await run(URI, f"SELECT no_such_column FROM {TABLE}", SELECTED)

    async def test_connection_failure_is_sanitized(self):
        bad = "postgresql://imyuvi@localhost:59999/no_such_db"
        with pytest.raises(DataSourceError) as excinfo:
            await run(bad, "SELECT 1", SELECTED)
        assert "localhost:59999" not in str(excinfo.value)
        assert "no_such_db" not in str(excinfo.value)

    async def test_oversized_sql_never_parses(self, table):
        big = f"SELECT * FROM {TABLE} WHERE name = '" + "a" * (100 * 1024) + "'"
        with pytest.raises(GuardError, match="100 KB"):
            await run(URI, big, SELECTED)


class TestDescribe:
    async def test_lists_the_table_with_columns(self, table):
        tables = await describe(URI)

        mine = [t for t in tables if t.name == TABLE]
        assert len(mine) == 1
        assert mine[0].schema == "public"
        names = {c.name for c in mine[0].columns}
        assert {"id", "name", "payload"} <= names

    async def test_excludes_system_schemas(self, table):
        tables = await describe(URI)
        schemas = {t.schema for t in tables}
        assert "pg_catalog" not in schemas
        assert "information_schema" not in schemas

    async def test_is_bounded(self, table):
        tables = await describe(URI)
        assert len(tables) <= 500
        assert all(len(t.columns) <= 200 for t in tables)

    async def test_connection_failure_is_sanitized(self):
        bad = "postgresql://imyuvi@localhost:59999/no_such_db"
        with pytest.raises(DataSourceError) as excinfo:
            await describe(bad)
        assert "localhost:59999" not in str(excinfo.value)
