"""MySQL executor integration tests (addendum 2026-11-05).

Run against a real MySQL only: set MYSQL_TEST_URI (e.g.
mysql://root:root@localhost:3306/mokinjay_ds_test). Skipped otherwise —
the guard's MySQL coverage is pure and always runs. To spin a throwaway
server up: docker run --rm -d -p 3306:3306 -e MYSQL_ROOT_PASSWORD=root
-e MYSQL_DATABASE=mokinjay_ds_test mysql:8
"""

import os

import pytest

from app.services.data_sources.mysql import DataSourceError, describe, run

MYSQL_URI = os.getenv("MYSQL_TEST_URI", "")
pytestmark = pytest.mark.skipif(
    not MYSQL_URI, reason="MYSQL_TEST_URI is not set — no MySQL to test against"
)


@pytest.fixture(scope="module")
def seeded():
    import pymysql

    conn = pymysql.connect(**_connect_kwargs(MYSQL_URI))
    with conn.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS orders")
        cursor.execute(
            "CREATE TABLE orders (id INT PRIMARY KEY AUTO_INCREMENT, "
            "status VARCHAR(20), total DECIMAL(10,2))"
        )
        for index in range(1, 206):
            cursor.execute(
                "INSERT INTO orders (status, total) VALUES (%s, %s)",
                ("paid" if index % 2 else "open", index * 1.5),
            )
    conn.commit()
    conn.close()
    yield


def _connect_kwargs(uri: str) -> dict:
    from urllib.parse import urlsplit

    parts = urlsplit(uri)
    return {
        "host": parts.hostname,
        "port": parts.port or 3306,
        "user": parts.username or "",
        "password": parts.password or "",
        "database": parts.path.lstrip("/") or None,
    }


ALLOWED = ["mokinjay_ds_test.orders"]


class TestRun:
    @pytest.mark.asyncio
    async def test_select_returns_rows_and_columns(self, seeded):
        result = await run(
            MYSQL_URI, "SELECT id, status FROM orders WHERE id = 1", ALLOWED
        )
        assert result.columns == ["id", "status"]
        assert result.rows == [[1, "paid"]]
        assert result.truncated is False

    @pytest.mark.asyncio
    async def test_row_cap_at_two_hundred(self, seeded):
        result = await run(MYSQL_URI, "SELECT id FROM orders", ALLOWED)
        assert result.row_count == 200
        assert result.truncated is True

    @pytest.mark.asyncio
    async def test_table_outside_allowlist_refused(self, seeded):
        with pytest.raises(Exception) as excinfo:
            await run(
                MYSQL_URI, "SELECT * FROM orders", ["mokinjay_ds_test.customers"]
            )
        assert "orders" in str(excinfo.value)

    @pytest.mark.asyncio
    async def test_max_execution_time_is_set(self, seeded):
        result = await run(
            MYSQL_URI, "SELECT @@SESSION.MAX_EXECUTION_TIME AS t", ALLOWED
        )
        assert result.rows == [[10000]]

    @pytest.mark.asyncio
    async def test_bad_credentials_are_sanitized(self, seeded):
        bad_uri = MYSQL_URI.replace("root:root", "root:wrong")
        with pytest.raises(DataSourceError) as excinfo:
            await run(bad_uri, "SELECT 1", ALLOWED)
        assert "root:wrong" not in str(excinfo.value)
        assert "mysql://" not in str(excinfo.value)


class TestDescribe:
    @pytest.mark.asyncio
    async def test_describe_lists_the_database_tables(self, seeded):
        tables = await describe(MYSQL_URI)
        names = [table.name for table in tables]
        assert "orders" in names
        assert all(table.schema == "mokinjay_ds_test" for table in tables)
        orders = next(table for table in tables if table.name == "orders")
        assert [column.name for column in orders.columns] == ["id", "status", "total"]
