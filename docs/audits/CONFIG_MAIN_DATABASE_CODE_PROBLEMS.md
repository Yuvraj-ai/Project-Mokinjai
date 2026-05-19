# Backend Config, Main, And Database Code Problems And Fix Plan

Scope reviewed:

- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/database.py`

This file is written as an implementation handoff for a CLI coding agent. Fix the problems in priority order, keep changes scoped, and add tests for configuration, app startup, and database-session behavior.

## Problem 1: Insecure Production Defaults Are Embedded In `config.py`

Evidence:

- `JWT_SECRET_KEY` defaults to `your-super-secret-key-change-in-production`.
- `MONGO_URL` defaults to a specific Atlas-style URL with a placeholder password.
- LLM API keys default to empty strings.
- There is no `ENVIRONMENT`, `DEBUG`, or production validation.

Why this is a problem:

- The app can start with an unsafe JWT secret.
- Placeholder infrastructure values can accidentally be used outside local development.
- Missing provider keys fail later at runtime instead of failing clearly at startup or returning a controlled feature error.

Proper fix:

Add environment awareness and validate dangerous defaults:

```python
from typing import Literal
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: Literal["local", "test", "production"] = "local"
    JWT_SECRET_KEY: SecretStr = Field(default=SecretStr("dev-only-change-me"))
    MONGO_URL: str = "mongodb://localhost:27017"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.ENVIRONMENT == "production":
            if self.JWT_SECRET_KEY.get_secret_value() in {
                "dev-only-change-me",
                "your-super-secret-key-change-in-production",
            }:
                raise ValueError("JWT_SECRET_KEY must be set in production")
            if "<db_password>" in self.MONGO_URL:
                raise ValueError("MONGO_URL contains a placeholder password")
        return self
```

Also update `.env.example` so sample values are local-safe and clearly placeholders.

Suggested tests:

- Production settings reject the default JWT secret.
- Production settings reject Mongo URLs containing `<db_password>`.
- Local settings can use local development defaults.

## Problem 2: Settings Are Captured At Import Time

Evidence:

- `main.py` sets `settings = get_settings()` at module import.
- `database.py` sets `settings = get_settings()` at module import and immediately creates the engine.
- Other utility modules do the same.

Why this is a problem:

- Tests that override environment variables after import cannot affect CORS, engine URL, or other configuration.
- App startup is harder to test because importing modules creates long-lived resources.
- Multiple app instances with different settings are not possible in the same process.

Proper fix:

Use factories and dependency injection.

For `main.py`:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(...)
    app.add_middleware(..., allow_origins=settings.cors_origins)
    include_routers(app)
    return app

app = create_app()
```

For `database.py`, add an engine/sessionmaker factory:

```python
def create_engine_for_settings(settings: Settings):
    return create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)

engine = create_engine_for_settings(get_settings())
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

For tests, expose a clean way to override the session dependency or build a test app with test settings.

Suggested tests:

- Build a test app with custom `FRONTEND_URL` or `CORS_ORIGINS` and assert middleware uses it.
- Build a test database sessionmaker without mutating global production settings.

## Problem 3: Database Engine Is Never Disposed On Shutdown

Evidence:

- `database.py` creates a global async engine.
- `main.py` has an empty lifespan function.
- There is no `await engine.dispose()` on shutdown.

Why this is a problem:

- Database connections can leak during tests and application shutdown.
- Reloading/dev server cycles can leave connections open longer than needed.

Proper fix:

Dispose the engine in lifespan:

```python
from app.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
```

If Mongo is used, close Mongo there too:

```python
from app.utils.mongo import MongoManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()
    MongoManager.close()
```

Suggested tests:

- Monkeypatch `engine.dispose` and assert it is called when lifespan exits.
- Monkeypatch `MongoManager.close` and assert it is called when lifespan exits.

## Problem 4: `get_db()` Does Not Explicitly Roll Back On Exceptions

Evidence:

- `get_db()` yields a session and always closes it.
- It does not call `rollback()` if route handling raises.

Why this is a problem:

- SQLAlchemy session close usually rolls back pending transactions, but relying on that is implicit.
- Explicit rollback makes failure behavior clearer and safer, especially when route code catches exceptions or reuses sessions in tests.

Proper fix:

```python
from collections.abc import AsyncGenerator

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

Suggested tests:

- Force a route dependency error after a DB mutation and assert `rollback()` is called.

## Problem 5: SQLite Foreign Keys Are Not Enabled

Evidence:

- Default `DATABASE_URL` is SQLite.
- Models rely on `ForeignKey(..., ondelete="CASCADE")` and `ondelete="SET NULL"`.
- SQLite does not enforce foreign keys unless `PRAGMA foreign_keys=ON` is enabled per connection.

Why this is a problem:

- Cascades and referential integrity may not work in local development/tests.
- Bugs can be hidden locally and appear only in Postgres or production.

Proper fix:

Enable SQLite foreign keys on connection creation.

For async SQLite, attach an event listener to the sync engine:

```python
from sqlalchemy import event

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)

if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
```

Suggested tests:

- In SQLite test DB, deleting a workspace cascades to workspace members.
- In SQLite test DB, deleting a workflow sets execution `workflow_id` to null if that is the model contract.

## Problem 6: Alembic URL Handling Conflicts With App Database Configuration

Evidence:

- `backend/app/config.py` defaults to SQLite.
- `backend/alembic.ini` has `sqlalchemy.url = postgresql://postgres:postgres@localhost:5432/agentbuilder`.
- `backend/alembic/env.py` overrides that with `settings.DATABASE_URL.replace("sqlite+aiosqlite", "sqlite")`.
- That replacement only handles SQLite async URLs. It does not handle `postgresql+asyncpg://...` to `postgresql://...` or other async drivers.

Why this is a problem:

- Migration behavior can differ from app runtime behavior.
- Switching to Postgres can break Alembic unless the URL is converted properly.
- Developers may be confused by the Postgres URL in `alembic.ini` while the app defaults to SQLite.

Proper fix:

Create a helper that converts async SQLAlchemy URLs to sync migration URLs:

```python
from sqlalchemy.engine import make_url

def get_sync_database_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername == "sqlite+aiosqlite":
        return str(url.set(drivername="sqlite"))
    if url.drivername == "postgresql+asyncpg":
        return str(url.set(drivername="postgresql"))
    return str(url)
```

Use the same helper in Alembic and tests. Update `alembic.ini` to make clear that the runtime value comes from settings.

Suggested tests:

- `sqlite+aiosqlite:///./x.db` converts to `sqlite:///./x.db`.
- `postgresql+asyncpg://user:pass@host/db` converts to `postgresql://user:pass@host/db`.

## Problem 7: CORS Configuration Supports Only One Origin

Evidence:

- `config.py` defines `FRONTEND_URL: str`.
- `main.py` uses `allow_origins=[settings.FRONTEND_URL]`.

Why this is a problem:

- Real deployments often need multiple origins: local dev, preview deployments, production frontend, admin tooling.
- A comma-separated env var would currently be treated as one invalid origin.

Proper fix:

Use a list setting:

```python
from pydantic import field_validator

class Settings(BaseSettings):
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value
```

Then:

```python
allow_origins=settings.CORS_ORIGINS
```

Suggested tests:

- `CORS_ORIGINS=http://localhost:5173,https://app.example.com` becomes a two-item list.
- CORS middleware receives both origins.

## Problem 8: Health Endpoint Is Too Shallow For Readiness

Evidence:

- `/health` returns only `{"status": "ok"}`.
- It does not check database, MongoDB, Redis/Celery, or required settings.

Why this is a problem:

- Deployment health checks can pass while the app cannot serve real requests.
- Debugging infrastructure failures is harder.

Proper fix:

Keep `/health` as a cheap liveness endpoint and add `/ready` for dependency readiness:

```python
@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/ready")
async def readiness_check():
    async with async_session() as session:
        await session.execute(text("SELECT 1"))
    await MongoManager.ping()
    return {"status": "ready"}
```

If Mongo is optional, report degraded status intentionally instead of failing blindly.

Suggested tests:

- `/health` returns ok without touching external services.
- `/ready` returns ready when DB/Mongo checks pass.
- `/ready` returns an error or degraded response when DB check fails.

## Problem 9: `main.py` Eager Router Imports Make App Import Fragile

Evidence:

- `main.py` imports all routers at module import:

  ```python
  from app.routers import auth, workspaces, workflows, executions, knowledge
  ```

- Current `workflows.py`, `executions.py`, and `schemas/execution.py` have syntax errors elsewhere in the tree, which means importing `app.main` is blocked.

Why this is a problem:

- One broken router prevents even health-check-only app import.
- Tests for unrelated app setup become blocked by unrelated route syntax errors.

Proper fix:

Primary fix:

- Fix the router/schema syntax errors.

Structural improvement:

- Move router inclusion into a helper so tests can import app factory pieces independently:

```python
def include_routers(app: FastAPI) -> None:
    from app.routers import auth, executions, knowledge, workflows, workspaces
    app.include_router(auth.router, ...)
```

Still fail fast during normal app creation, but make small unit tests for config/database less coupled to routers.

Suggested tests:

- `python -c "from app.main import app"` passes after router syntax fixes.
- `create_app()` includes expected route prefixes.

## Problem 10: Users Router Is Not Included Or Removed

Evidence:

- `backend/app/routers/users.py` exists as an empty placeholder.
- `main.py` does not include `users.router`.

Why this is a problem:

- Future agents may add user endpoints to `users.py` and assume they are reachable.
- The routing structure is ambiguous.

Proper fix:

Pick one:

- Delete `users.py` if user routes intentionally live in `auth.py`.
- Or include it intentionally:

  ```python
  from app.routers import users
  app.include_router(users.router, prefix="/api/users", tags=["users"])
  ```

Suggested tests:

- If kept, route listing includes `/api/users`.
- If deleted, no imports reference `app.routers.users`.

## Problem 11: Database Base Lacks Naming Convention Metadata

Evidence:

- `Base` is a plain `DeclarativeBase`.
- Alembic is configured for autogeneration.
- Models will need constraints and indexes for roles/statuses/version uniqueness.

Why this is a problem:

- Alembic autogenerate can produce unstable or unnamed constraints.
- Dropping/modifying constraints is harder across databases.

Proper fix:

Use SQLAlchemy `MetaData` with naming conventions:

```python
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)
```

Suggested verification:

- Alembic autogenerate gives deterministic constraint names.

## Problem 12: Engine Options Are Not Environment-Specific

Evidence:

- `create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)` is hardcoded.
- There are no settings for SQL echo, pool size, max overflow, pool recycle, or connect args.

Why this is a problem:

- Production and local development often need different pool behavior.
- Debugging SQL can require toggling echo without editing code.
- SQLite and Postgres need different practical options.

Proper fix:

Add settings:

```python
DB_ECHO: bool = False
DB_POOL_SIZE: int = 5
DB_MAX_OVERFLOW: int = 10
DB_POOL_RECYCLE_SECONDS: int = 1800
```

Build engine kwargs based on URL dialect:

```python
kwargs = {"echo": settings.DB_ECHO, "pool_pre_ping": True}
if not settings.DATABASE_URL.startswith("sqlite"):
    kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    )
engine = create_async_engine(settings.DATABASE_URL, **kwargs)
```

Suggested tests:

- SQLite engine creation does not receive unsupported pool args.
- Postgres engine creation includes configured pool args.

## Recommended Implementation Order

1. Add production-safe settings validation and update `.env.example`.
2. Fix router/schema syntax errors so `app.main` can import.
3. Add app factory and avoid unnecessary import-time settings/resource capture.
4. Add lifespan cleanup for DB and Mongo.
5. Make `get_db()` explicitly rollback on exceptions.
6. Enable SQLite foreign keys.
7. Fix Alembic sync URL conversion.
8. Replace `FRONTEND_URL` with `CORS_ORIGINS`.
9. Add readiness checks.
10. Decide whether to include or remove `users.py`.
11. Add metadata naming convention and environment-specific engine options.

## Verification Commands

Run these after implementing fixes:

```bash
python -m py_compile backend/app/config.py backend/app/main.py backend/app/database.py

cd backend
python - <<'PY'
from app.config import get_settings
from app.main import app
from app.database import engine
print("settings/app/database imports ok", len(app.routes))
PY

pytest tests -q
```

Also verify Alembic URL conversion:

```bash
cd backend
alembic current
```

## Notes For The CLI Agent

- Do not edit unrelated frontend files.
- Preserve existing user-owned uncommitted changes in `config.py` and `main.py` unless the fix must build on them.
- Keep config changes aligned with `.env.example`, Alembic, Celery, Mongo utilities, and tests.
- Do not require live MongoDB or Redis for unit tests; mock readiness checks where appropriate.
- The current shell used for this report does not have FastAPI/SQLAlchemy installed, so full import/runtime verification must run in a compatible backend environment.
