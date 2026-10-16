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


@dataclass(frozen=True)
class SeedResult:
    """What the seed did, so a re-run reports rather than asserts success vaguely."""

    user_id: str
    user_created: bool
    workspace_id: str
    workspace_created: bool
    membership_created: bool


async def seed_admin_and_workspace(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    name: str = "Administrator",
    workspace_name: str = "Default",
    is_superuser: bool = True,
) -> SeedResult:
    """Get-or-create a user, a workspace owned by them, and the membership joining them.

    Idempotent: every step is a lookup followed by a conditional insert, and the
    single commit at the end means a failure leaves the database unchanged
    rather than half-seeded.

    An existing user is left exactly as found. The password is not reset and the
    superuser flag is not raised -- changing an existing account's credentials or
    privileges is not a seeding action.
    """
    await assert_schema_present(db)

    user = (
        await db.execute(select(User).where(User.email == email))
    ).scalars().first()
    user_created = user is None
    if user is None:
        user = User(
            name=name,
            email=email,
            hashed_password=hash_password(password),
            is_superuser=is_superuser,
        )
        db.add(user)
        # The id is a Python-side default, so it is only populated after a flush.
        await db.flush()

    # Workspace names are not unique in the model, so ownership is part of the
    # identity. This matches the hand-created row this script reproduces.
    workspace = (
        await db.execute(
            select(Workspace).where(
                Workspace.owner_id == user.id,
                Workspace.name == workspace_name,
            )
        )
    ).scalars().first()
    workspace_created = workspace is None
    if workspace is None:
        workspace = Workspace(name=workspace_name, owner_id=user.id)
        db.add(workspace)
        await db.flush()

    membership = (
        await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.user_id == user.id,
            )
        )
    ).scalars().first()
    membership_created = membership is None
    if membership is None:
        db.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
        )

    await db.commit()

    result = SeedResult(
        user_id=user.id,
        user_created=user_created,
        workspace_id=workspace.id,
        workspace_created=workspace_created,
        membership_created=membership_created,
    )
    logger.info(
        f"Seed: user {user.id} (created={user_created}), "
        f"workspace {workspace.id} (created={workspace_created}), "
        f"membership created={membership_created}"
    )
    return result
