import os
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.workflow import Workflow
from app.models.execution import Execution
from app.utils.security import hash_password, create_access_token


# Load the repo-root .env so TEST_DATABASE_URL works as documented. Settings
# loads .env through pydantic-settings, which does not populate os.environ, so
# without this an os.getenv() read would never see a .env entry. A missing file
# is fine — the hardcoded default below is the fallback.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://imyuvi@localhost:5432/mokinjay_test"
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


def _database_name(url: str) -> str:
    """The database name in a URL, ignoring any query string."""
    return url.rsplit("/", 1)[-1].split("?")[0]


def assert_disposable(url: str) -> None:
    """Refuse any database that is not unmistakably disposable.

    The suite drops and truncates every table on each run. Without this guard a
    misconfigured URL would destroy the development database, or the hosted one.
    """
    name = _database_name(url)
    if not name.endswith("_test"):
        raise RuntimeError(
            f"TEST_DATABASE_URL must name a database ending in '_test'; got "
            f"{name!r}. The suite truncates every table it can see."
        )


assert_disposable(TEST_DATABASE_URL)


@pytest_asyncio.fixture(scope="session")
async def engine():
    """One schema for the whole session; rows are cleared per test instead."""
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def clean_tables(engine):
    """Empty every table before each test, so tests cannot see each other's rows."""
    names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture(scope="function")
async def db_session(session_factory):
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session):
    user = User(
        email="test@example.com",
        hashed_password=hash_password("testpass123"),
        name="Test User",
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def admin_user(db_session):
    user = User(
        email="admin@example.com",
        hashed_password=hash_password("adminpass123"),
        name="Admin User",
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_user, db_session):
    from app.services.sessions import create_session

    session = await create_session(
        db_session, user_id=test_user.id, refresh_token="fixture-refresh-token"
    )
    token = create_access_token(
        {"sub": test_user.id, "email": test_user.email, "sid": session.id}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def admin_headers(admin_user, db_session):
    from app.services.sessions import create_session

    session = await create_session(
        db_session, user_id=admin_user.id, refresh_token="fixture-admin-refresh-token"
    )
    token = create_access_token(
        {"sub": admin_user.id, "email": admin_user.email, "sid": session.id}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def test_workspace(db_session, test_user):
    workspace = Workspace(
        name="Test Workspace",
        owner_id=test_user.id,
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=test_user.id,
        role="owner",
    )
    db_session.add(member)
    await db_session.commit()
    return workspace


@pytest_asyncio.fixture(scope="function")
async def test_workflow(db_session, test_workspace, test_user):
    workflow = Workflow(
        workspace_id=test_workspace.id,
        name="Test Workflow",
        flow_definition={
            "nodes": [
                {"id": "node_1", "type": "input", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "node_2", "type": "output", "position": {"x": 200, "y": 0}, "data": {"format": "text"}},
            ],
            "edges": [
                {"id": "edge_1", "source": "node_1", "target": "node_2", "sourceHandle": None, "targetHandle": None},
            ],
        },
        status="draft",
        version=1,
        created_by=test_user.id,
    )
    db_session.add(workflow)
    await db_session.commit()
    await db_session.refresh(workflow)
    return workflow
