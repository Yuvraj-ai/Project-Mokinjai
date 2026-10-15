import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

# Make `app` importable, then load the repo-root .env so DATABASE_URL is
# available. The path is absolute and CWD-independent, matching the rule in
# app/config.py, so the app and Alembic always resolve the same file and the
# same database. (The previous `dirname(__file__)/../.env` resolved to
# backend/.env, which does not exist, so this loaded nothing.)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from app.database import Base
from app.models import *  # noqa: F401,F403 - register every model for autogenerate

config = context.config

# --- Safety rail: never run DDL against a remote database by accident -------
# Alembic is invoked by `alembic upgrade head`, which every documented local
# path runs (run_mokinjay.sh on each launch, and the README/manual recipes). The
# repo-root .env points DATABASE_URL at the hosted production database, so
# without this a routine local command would silently execute migrations there.
# Migrating a remote database is therefore an explicit act, opt into it here.
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_ALLOW_REMOTE_ENV_VAR = "ALLOW_REMOTE_MIGRATIONS"


def assert_local_target(url: str | None) -> None:
    """Refuse a remote migration host unless ALLOW_REMOTE_MIGRATIONS=1 is set."""
    if not url:
        return
    host = make_url(url).host
    if host is None or host in _LOCAL_HOSTS:
        return
    if os.getenv(_ALLOW_REMOTE_ENV_VAR) == "1":
        return
    sys.stderr.write(
        f"\nRefusing to run migrations against the remote host {host!r}.\n"
        f"Migrations execute DDL, and this is not a local database.\n"
        f"If you really mean to migrate {host}, set {_ALLOW_REMOTE_ENV_VAR}=1.\n\n"
    )
    raise SystemExit(1)


# One source of truth for the URL. alembic.ini deliberately holds none.
# The guard runs first: the URL can carry a URL-encoded '%' in a password, which
# configparser rejects, and a refusal must read as a message rather than a
# traceback.
database_url = os.getenv("DATABASE_URL")
assert_local_target(database_url)

if database_url:
    # configparser treats '%' as interpolation syntax, so escape it; the value
    # read back through get_section/get_main_option is unescaped again.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
