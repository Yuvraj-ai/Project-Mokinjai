"""The migrations and the models must describe the same schema.

A divergence means a database built by `alembic upgrade head` differs from one
built by `Base.metadata.create_all`, so tests and development would exercise a
different schema than a migrated deployment. This build a scratch database purely
from the migrations and compares it column by column against the models.

This is the check that, run by hand, found three real divergences that every code
review had missed: `llm_profiles` and `structured_outputs` declared their
timestamps nullable with no server default in the migrations, and
`users.is_superuser` carried a server default the model lacked.

Nullability and the *presence* of a server default are compared, not the literal
default text, because the two sides spell `now()` and `false` differently and
comparing strings would produce noise rather than signal. DDL cannot express
`onupdate`, so that is deliberately out of scope.
"""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg

from app.database import Base
from unit_tests.conftest import TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Build the scratch database beside the test database, on the same server, so the
# check follows whatever TEST_DATABASE_URL points at rather than assuming a host.
_plain = TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
_parts = urlsplit(_plain)
_test_db_name = _parts.path.lstrip("/")
SCRATCH_DB = f"{_test_db_name}_parity"

ADMIN_DSN = urlunsplit((_parts.scheme, _parts.netloc, "/postgres", "", ""))
SCRATCH_DSN = urlunsplit((_parts.scheme, _parts.netloc, f"/{SCRATCH_DB}", "", ""))
SCRATCH_SQLALCHEMY_URL = urlunsplit(
    ("postgresql+asyncpg", _parts.netloc, f"/{SCRATCH_DB}", "", "")
)


async def _on_admin(statement: str) -> None:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        await conn.execute(statement)
    finally:
        await conn.close()


def _run_migrations() -> None:
    """Apply the migrations to the scratch database, exactly as a human would."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env={**os.environ, "DATABASE_URL": SCRATCH_SQLALCHEMY_URL},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"alembic upgrade head failed against {SCRATCH_DB}:\n"
        f"{result.stdout}\n{result.stderr}"
    )


async def _migrated_columns() -> dict[tuple[str, str], tuple[bool, bool]]:
    """(nullable, has_server_default) per column, read from the migrated schema."""
    conn = await asyncpg.connect(SCRATCH_DSN)
    try:
        rows = await conn.fetch(
            """
            select table_name, column_name, is_nullable, column_default
            from information_schema.columns
            where table_schema = 'public'
              and table_name <> 'alembic_version'
            """
        )
    finally:
        await conn.close()

    return {
        (row["table_name"], row["column_name"]): (
            row["is_nullable"] == "YES",
            row["column_default"] is not None,
        )
        for row in rows
    }


def _model_columns() -> dict[tuple[str, str], tuple[bool, bool]]:
    """(nullable, has_server_default) per column, read from the ORM models."""
    return {
        (table.name, column.name): (
            bool(column.nullable),
            column.server_default is not None,
        )
        for table in Base.metadata.sorted_tables
        for column in table.columns
    }


async def test_migrated_schema_matches_the_models():
    await _on_admin(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')
    try:
        await _on_admin(f'CREATE DATABASE "{SCRATCH_DB}"')
        _run_migrations()
        migrated = await _migrated_columns()
    finally:
        await _on_admin(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)')

    declared = _model_columns()

    problems: list[str] = []
    for key in sorted(set(migrated) - set(declared)):
        problems.append(f"{key[0]}.{key[1]}: created by a migration but absent from the models")
    for key in sorted(set(declared) - set(migrated)):
        problems.append(f"{key[0]}.{key[1]}: declared on a model but no migration creates it")
    for key in sorted(set(migrated) & set(declared)):
        if migrated[key] != declared[key]:
            problems.append(
                f"{key[0]}.{key[1]}: migrations give "
                f"(nullable={migrated[key][0]}, default={migrated[key][1]}) "
                f"but the model declares "
                f"(nullable={declared[key][0]}, default={declared[key][1]})"
            )

    assert not problems, (
        "the migrated schema and the models disagree:\n  " + "\n  ".join(problems)
    )
