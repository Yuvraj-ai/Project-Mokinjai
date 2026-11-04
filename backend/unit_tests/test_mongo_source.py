"""MongoDB executor integration tests (addendum 2026-11-05).

Run against a real MongoDB only: set MONGO_TEST_URI (e.g.
mongodb://localhost:27017). Skipped otherwise — the guard's coverage is
pure and always runs. To spin a throwaway server up:
docker run --rm -d -p 27017:27017 mongo:7
"""

import os

import pytest

from app.services.data_sources.mongo import DataSourceError, describe, run_find

MONGO_URI = os.getenv("MONGO_TEST_URI", "")
pytestmark = pytest.mark.skipif(
    not MONGO_URI, reason="MONGO_TEST_URI is not set — no MongoDB to test against"
)

DATABASE = "mokinjay_ds_test"
ALLOWED = ["orders", "customers"]


@pytest.fixture(scope="module")
def seeded():
    from pymongo import MongoClient

    client = MongoClient(MONGO_URI)
    collection = client[DATABASE]["orders"]
    collection.drop()
    collection.insert_many(
        [
            {"status": "paid" if index % 2 else "open", "total": index * 1.5}
            for index in range(1, 206)
        ]
    )
    client[DATABASE]["customers"].insert_one({"name": "Acme"})
    yield
    client.drop_database(DATABASE)
    client.close()


class TestRunFind:
    @pytest.mark.asyncio
    async def test_find_returns_documents(self, seeded):
        result = await run_find(
            MONGO_URI, DATABASE, "orders", ALLOWED, '{"status": "open"}'
        )
        assert result.row_count == 102
        assert "status" in result.columns and "total" in result.columns
        assert result.truncated is False

    @pytest.mark.asyncio
    async def test_row_cap_at_two_hundred(self, seeded):
        result = await run_find(MONGO_URI, DATABASE, "orders", ALLOWED, "{}")
        assert result.row_count == 200
        assert result.truncated is True

    @pytest.mark.asyncio
    async def test_limit_is_honored_and_flags_more_matches(self, seeded):
        # truncated means "more matched than returned", so an explicit limit
        # with more matches behind it reports it too.
        result = await run_find(MONGO_URI, DATABASE, "orders", ALLOWED, "{}", limit=5)
        assert result.row_count == 5
        assert result.truncated is True

    @pytest.mark.asyncio
    async def test_projection_narrows_fields(self, seeded):
        # Mongo returns _id alongside included fields unless excluded.
        result = await run_find(
            MONGO_URI, DATABASE, "orders", ALLOWED, '{"status": "paid"}', '{"total": 1}'
        )
        assert set(result.columns) == {"_id", "total"}
        assert all(row[result.columns.index("total")] > 0 for row in result.rows)

    @pytest.mark.asyncio
    async def test_where_operator_refused_before_any_dial(self, seeded):
        with pytest.raises(Exception, match=r"\$where"):
            await run_find(
                MONGO_URI, DATABASE, "orders", ALLOWED, '{"$where": "true"}'
            )

    @pytest.mark.asyncio
    async def test_unselected_collection_refused(self, seeded):
        with pytest.raises(Exception, match="users"):
            await run_find(MONGO_URI, DATABASE, "users", ALLOWED, "{}")


class TestDescribe:
    @pytest.mark.asyncio
    async def test_describe_lists_collections_with_sampled_fields(self, seeded):
        tables = await describe(MONGO_URI, database=DATABASE)
        names = [table.name for table in tables]
        assert "orders" in names and "customers" in names
        assert all(table.schema == DATABASE for table in tables)
        orders = next(table for table in tables if table.name == "orders")
        field_names = {column.name for column in orders.columns}
        assert {"status", "total"} <= field_names
