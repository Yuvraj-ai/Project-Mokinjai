"""Guards that keep the suite on PostgreSQL.

SQLite was retired (spec 2026-10-15). These exist so the SQLite test path cannot
be reintroduced quietly, and so conftest's safety guard is proven rather than
trusted.
"""

import pytest
from sqlalchemy import text

from unit_tests import conftest


async def test_suite_runs_on_postgresql(engine):
    assert engine.dialect.name == "postgresql"


async def test_server_reports_itself_as_postgresql(engine):
    async with engine.connect() as conn:
        version = (await conn.execute(text("select version()"))).scalar()
    assert "PostgreSQL" in version


def test_guard_accepts_a_disposable_database():
    conftest.assert_disposable("postgresql+asyncpg://u@h:5432/mokinjay_test")


def test_guard_rejects_the_development_database():
    with pytest.raises(RuntimeError):
        conftest.assert_disposable("postgresql+asyncpg://u@h:5432/mokinjay")


def test_guard_rejects_a_hosted_database():
    with pytest.raises(RuntimeError):
        conftest.assert_disposable(
            "postgresql+asyncpg://u:p@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
        )


def test_guard_ignores_query_parameters():
    conftest.assert_disposable("postgresql+asyncpg://u@h:5432/mokinjay_test?ssl=require")
