"""The seed script's reusable core.

Run against the normal ``db_session`` fixture: the point of putting the logic in
``app.services`` rather than in the CLI is that it needs no subprocess and no
second database to be tested.
"""

import os
from pathlib import Path

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
from app.services.seed import SeedResult, assert_schema_present, seed_admin_and_workspace
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


from seed import describe_target, format_summary, requires_confirmation, resolve_password


class _Args:
    def __init__(self, password=None, generate_password=False):
        self.password = password
        self.generate_password = generate_password


def test_describe_target_returns_host_and_database_only():
    host, database = describe_target(
        "postgresql+asyncpg://someuser:somesecret@db.example.com:5432/mokinjay"
    )
    assert host == "db.example.com"
    assert database == "mokinjay"


def test_describe_target_leaks_no_credentials():
    """The target is printed before writing, so it must carry no secrets."""
    host, database = describe_target(
        "postgresql+asyncpg://someuser:somesecret@db.example.com:5432/mokinjay"
    )
    assert "somesecret" not in host
    assert "somesecret" not in database
    assert "someuser" not in host


def test_local_hosts_need_no_confirmation():
    for host in ("localhost", "127.0.0.1", ""):
        assert requires_confirmation(host) is False


def test_remote_hosts_need_confirmation():
    assert requires_confirmation("db.example.com") is True


def test_resolve_password_prefers_an_explicit_flag(monkeypatch):
    monkeypatch.setenv("MOKINJAY_SEED_PASSWORD", "from-env")
    password, generated = resolve_password(_Args(password="from-flag"), os.environ)
    assert password == "from-flag"
    assert generated is False


def test_resolve_password_falls_back_to_the_environment(monkeypatch):
    monkeypatch.setenv("MOKINJAY_SEED_PASSWORD", "from-env")
    password, generated = resolve_password(_Args(), os.environ)
    assert password == "from-env"
    assert generated is False


def test_resolve_password_generates_a_long_one_when_asked():
    password, generated = resolve_password(_Args(generate_password=True), {})
    assert generated is True
    assert len(password) >= 20


def test_summary_cannot_contain_the_password():
    """``format_summary`` does not take the password as a parameter.

    That is a structural guarantee rather than a checked one: there is no code
    path by which the credential can reach the summary text.
    """
    result = SeedResult(
        user_id="u1",
        user_created=True,
        workspace_id="w1",
        workspace_created=False,
        membership_created=False,
    )
    text = format_summary(result, host="localhost", database="mokinjay")
    assert "u1" in text
    assert "w1" in text
    assert "localhost" in text
    assert "mokinjay" in text


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_create_user_script_does_not_build_schema():
    """It must not build a schema outside Alembic (ADR-022).

    Asserted against the source, in the style ``test_secret_scripts.py`` already
    uses for script-level invariants: this is a property of the file, not of any
    function's behaviour, so there is nothing to call.
    """
    source = (BACKEND_DIR / "create_user.py").read_text()
    assert "create_all" not in source
    assert "assert_schema_present" in source
