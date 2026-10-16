"""The seed script's reusable core.

Run against the normal ``db_session`` fixture: the point of putting the logic in
``app.services`` rather than in the CLI is that it needs no subprocess and no
second database to be tested.
"""

import pytest

from app.services.seed import assert_schema_present


async def test_assert_schema_present_accepts_a_migrated_database(db_session):
    # The test database is built by the suite; this must not raise.
    await assert_schema_present(db_session)


async def test_assert_schema_present_names_the_migration_command(db_session):
    """A database without a schema is a mistake to report, not to paper over.

    ``table`` is a parameter precisely so this branch can be exercised without
    dismantling the test database.
    """
    with pytest.raises(RuntimeError) as excinfo:
        await assert_schema_present(db_session, table="public.definitely_not_a_table")

    assert "alembic upgrade head" in str(excinfo.value)
