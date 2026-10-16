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


from sqlalchemy import func, select

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.services.seed import assert_schema_present, seed_admin_and_workspace
from app.utils.security import verify_password

SEED = dict(email="admin@mokinjay.local", password="correct-horse-battery-staple")


async def _count(db, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar()


async def test_seed_creates_user_workspace_and_owner_membership(db_session):
    result = await seed_admin_and_workspace(db_session, **SEED)

    assert result.user_created is True
    assert result.workspace_created is True
    assert result.membership_created is True

    user = (
        await db_session.execute(select(User).where(User.email == SEED["email"]))
    ).scalars().first()
    assert user is not None
    assert user.id == result.user_id
    assert user.is_superuser is True

    workspace = (
        await db_session.execute(select(Workspace).where(Workspace.id == result.workspace_id))
    ).scalars().first()
    assert workspace is not None
    assert workspace.owner_id == user.id

    membership = (
        await db_session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == result.workspace_id,
                WorkspaceMember.user_id == user.id,
            )
        )
    ).scalars().first()
    assert membership is not None
    assert membership.role == "owner"


async def test_seed_is_idempotent(db_session):
    """A re-run must be a legible no-op, not a second set of rows."""
    first = await seed_admin_and_workspace(db_session, **SEED)
    second = await seed_admin_and_workspace(db_session, **SEED)

    assert second.user_id == first.user_id
    assert second.workspace_id == first.workspace_id
    assert second.user_created is False
    assert second.workspace_created is False
    assert second.membership_created is False

    assert await _count(db_session, User) == 1
    assert await _count(db_session, Workspace) == 1
    assert await _count(db_session, WorkspaceMember) == 1


async def test_seed_stores_a_hash_not_the_password(db_session):
    """A seed script is exactly where a plaintext password would go unnoticed."""
    await seed_admin_and_workspace(db_session, **SEED)

    user = (
        await db_session.execute(select(User).where(User.email == SEED["email"]))
    ).scalars().first()
    assert user.hashed_password != SEED["password"]
    assert verify_password(SEED["password"], user.hashed_password) is True


async def test_seed_honours_the_is_superuser_flag(db_session):
    result = await seed_admin_and_workspace(
        db_session, email="plain@mokinjay.local", password="pw", is_superuser=False
    )

    user = (
        await db_session.execute(select(User).where(User.id == result.user_id))
    ).scalars().first()
    assert user.is_superuser is False


async def test_seed_adds_a_membership_to_an_existing_user(db_session):
    """The partial-repair case: the account survived but owns nothing.

    A naive get-or-create on the user would return early and leave the account
    able to authenticate but unable to do anything -- which is the defect.
    """
    first = await seed_admin_and_workspace(db_session, **SEED)

    membership = (
        await db_session.execute(
            select(WorkspaceMember).where(WorkspaceMember.user_id == first.user_id)
        )
    ).scalars().first()
    await db_session.delete(membership)
    await db_session.commit()

    second = await seed_admin_and_workspace(db_session, **SEED)

    assert second.user_created is False
    assert second.workspace_created is False
    assert second.membership_created is True
    assert await _count(db_session, WorkspaceMember) == 1


async def test_seed_does_not_elevate_an_existing_non_superuser(db_session):
    """Silently granting administrator is the side effect a seed must not have."""
    await seed_admin_and_workspace(
        db_session, email="existing@mokinjay.local", password="pw", is_superuser=False
    )

    await seed_admin_and_workspace(
        db_session, email="existing@mokinjay.local", password="other", is_superuser=True
    )

    user = (
        await db_session.execute(select(User).where(User.email == "existing@mokinjay.local"))
    ).scalars().first()
    assert user.is_superuser is False
