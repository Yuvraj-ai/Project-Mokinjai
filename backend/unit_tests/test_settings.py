"""Settings surface.

The sync database URL existed only so Alembic could use a blocking driver. Now
that Alembic is async there is exactly one database URL, and this test keeps a
second one from creeping back in.
"""

from app.config import get_settings


def test_settings_no_longer_expose_a_sync_database_url():
    assert not hasattr(get_settings(), "SYNC_DATABASE_URL")


def test_database_url_uses_the_async_driver():
    assert get_settings().DATABASE_URL.startswith("postgresql+asyncpg://")
