"""Provision the minimum rows needed to use the application.

Idempotent by design. This is the documented recovery step for a database that
has been reset, so it must be safe to run against a database that is already
usable -- which means it must never refuse merely because its work is done.

Seeding is data; migrations are schema. This module never builds a schema.
"""

from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import logger
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.utils.security import hash_password


async def assert_schema_present(db: AsyncSession, table: str = "public.users") -> None:
    """Fail loudly when the schema has not been migrated.

    This replaces a ``create_all`` call. Building the schema from the models here
    would bypass Alembic and leave the database unable to accept migrations,
    which is a worse state than an empty one -- it looks like it worked.

    ``table`` is a parameter so the failure branch is testable without
    dismantling the test database.
    """
    result = await db.execute(text("SELECT to_regclass(:name)"), {"name": table})
    if result.scalar() is None:
        raise RuntimeError(
            f"Table {table} does not exist, so the schema has not been migrated. "
            "Run `alembic upgrade head` first. This script seeds data and never "
            "builds schema."
        )
