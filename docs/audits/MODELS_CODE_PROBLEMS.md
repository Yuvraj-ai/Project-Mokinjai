# Backend Models Code Problems And Fix Plan

Scope reviewed: `backend/app/models`.

The user asked for `backend/app/model`; this repository has `backend/app/models`, so this report reviews that package. It is written as a handoff for a CLI coding agent: each finding includes evidence, impact, the proper fix, and suggested verification.

## Current Files

- `backend/app/models/__init__.py`
- `backend/app/models/api_key.py`
- `backend/app/models/execution.py`
- `backend/app/models/knowledge.py`
- `backend/app/models/user.py`
- `backend/app/models/workflow.py`
- `backend/app/models/workspace.py`

## Problem 1: `Workflow` Storage Contract Is Broken After Moving Flow Data To MongoDB

Evidence:

- `backend/app/models/workflow.py` defines `Workflow.mongo_flow_id`, but no longer defines `Workflow.flow_definition`.
- `backend/app/routers/workflows.py` still creates and updates workflows with `flow_definition=...` and `workflow.flow_definition = ...`.
- `backend/app/routers/executions.py` still checks `workflow.flow_definition.get("nodes")`.
- `WorkflowVersion` defines `mongo_flow_id`, but `workflows.py` creates it with `flow_definition=workflow.flow_definition`.

Why this is a problem:

- `Workflow(flow_definition=...)` will fail because `flow_definition` is not a mapped model attribute.
- `workflow.flow_definition` reads and writes will fail with `AttributeError`.
- `WorkflowVersion(flow_definition=...)` will fail because `WorkflowVersion` also has no `flow_definition` column.
- Workflow creation, update, versioning, and execution can all break at runtime.

Proper fix:

1. Pick one storage strategy and make models, routers, schemas, executor, and migrations agree.

2. Recommended strategy, because the current model already points this way: keep large flow JSON in MongoDB and store only `mongo_flow_id` in SQL.

3. Update workflow create:

   ```python
   flow_id = await BlobService.save_blob(request.flow_definition.model_dump())
   workflow = Workflow(
       workspace_id=workspace_id,
       name=request.name,
       description=request.description,
       mongo_flow_id=flow_id,
       created_by=current_user.id,
   )
   ```

4. Update workflow update:

   ```python
   if request.flow_definition is not None:
       flow_data = request.flow_definition.model_dump()
       if workflow.mongo_flow_id:
           await BlobService.update_blob(workflow.mongo_flow_id, flow_data)
           version_flow_id = await BlobService.save_blob(flow_data)
       else:
           workflow.mongo_flow_id = await BlobService.save_blob(flow_data)
           version_flow_id = workflow.mongo_flow_id

       workflow.version += 1
       db.add(
           WorkflowVersion(
               workflow_id=workflow.id,
               version=workflow.version,
               mongo_flow_id=version_flow_id,
               created_by=current_user.id,
           )
       )
   ```

5. Update execution precheck to load the blob before checking nodes:

   ```python
   flow_def = await BlobService.get_blob(workflow.mongo_flow_id)
   if not flow_def or not flow_def.get("nodes"):
       raise BadRequestException("Workflow has no nodes to execute")
   ```

6. Keep `WorkflowResponse.flow_definition` as an API response field, but populate it from MongoDB manually as `get_workflow()` already tries to do.

Alternative acceptable fix:

- Re-add `flow_definition: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)` to `Workflow` and `WorkflowVersion` and stop using `mongo_flow_id` for flow definitions.
- This is simpler but conflicts with the newer `BlobService` direction.

Suggested tests:

- Creating a workflow stores a Mongo blob and saves `mongo_flow_id`.
- Fetching a workflow returns `flow_definition` hydrated from MongoDB.
- Updating a workflow increments `version`, updates/stores blob data, and creates a `WorkflowVersion` with `mongo_flow_id`.
- Executing a workflow with no nodes returns `400` instead of raising `AttributeError`.

## Problem 2: `WorkflowVersion.__table_args__` Does Not Add The Intended Unique Constraint

Evidence:

- `backend/app/models/workflow.py` says:

  ```python
  __table_args__ = (
      # Unique constraint on workflow_id + version
      {"sqlite_autoincrement": True},
  )
  ```

- There is no `UniqueConstraint`.
- `sqlite_autoincrement` is irrelevant with the current string UUID primary key.

Why this is a problem:

- Duplicate version numbers can be inserted for the same workflow.
- The comment says a safety rule exists, but the database does not enforce it.

Proper fix:

```python
from sqlalchemy import UniqueConstraint

__table_args__ = (
    UniqueConstraint("workflow_id", "version", name="uq_workflow_versions_workflow_id_version"),
)
```

Also add an index if versions are frequently listed:

```python
Index("ix_workflow_versions_workflow_id_created_at", "workflow_id", "created_at")
```

Suggested tests:

- Inserting two `WorkflowVersion` rows with the same `workflow_id` and `version` should raise an integrity error.

## Problem 3: PostgreSQL-Only `JSONB` Is Used While The App Defaults To SQLite

Evidence:

- `backend/app/config.py` defaults to `sqlite+aiosqlite:///./agentbuilder.db`.
- `backend/alembic/env.py` rewrites the async SQLite URL to a sync SQLite URL for migrations.
- `backend/app/models/api_key.py` imports `JSONB` from `sqlalchemy.dialects.postgresql`.
- `AuditLog.metadata_` uses `mapped_column("metadata", JSONB, nullable=True)`.
- `INET` is imported but unused.

Why this is a problem:

- SQLite cannot create a PostgreSQL `JSONB` column.
- Alembic autogeneration or database creation can fail in the default development configuration.
- The unused `INET` import suggests an unfinished database-specific type decision.

Proper fix:

If SQLite support is required, use portable SQLAlchemy JSON:

```python
from sqlalchemy import JSON

metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
```

If PostgreSQL is the real target, change the app default config, Alembic URL handling, and local setup docs to Postgres, then keep `JSONB`.

Recommended for this repo right now:

- Replace `JSONB` with portable `JSON`.
- Remove the unused `INET` import.
- Keep `ip_address` as `String(45)` for IPv4/IPv6 portability.

Suggested verification:

```bash
python - <<'PY'
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import sqlite
from app.database import Base
import app.models  # noqa
for table in Base.metadata.sorted_tables:
    str(CreateTable(table).compile(dialect=sqlite.dialect()))
print("sqlite model DDL compiles")
PY
```

## Problem 4: Important Model State Fields Are Plain Strings With No Database Constraints

Evidence:

- `WorkspaceMember.role` is a free string.
- `Workflow.status` is a free string.
- `Execution.status` and `Execution.trigger_type` are free strings.
- `KnowledgeBase.type` is a free string.
- `Document.status` is a free string.

Why this is a problem:

- Invalid values can enter the database and break authorization or UI assumptions.
- A typo like `"publshed"` or `"edtor"` persists silently.
- Middleware RBAC currently relies on exact role strings.

Proper fix:

Add shared constants and database `CheckConstraint`s, or use SQLAlchemy enums consistently.

Portable `CheckConstraint` example:

```python
from sqlalchemy import CheckConstraint

ROLE_VALUES = ("owner", "admin", "editor", "viewer")

__table_args__ = (
    CheckConstraint(
        "role in ('owner', 'admin', 'editor', 'viewer')",
        name="ck_workspace_members_role",
    ),
)
```

Apply the same pattern:

- `Workflow.status`: `draft`, `published`, `archived`
- `Execution.status`: `pending`, `running`, `completed`, `failed`, `cancelled`
- `Execution.trigger_type`: `manual`, `api`, `scheduled`, `webhook`
- `KnowledgeBase.type`: `document`, `url`, `api`
- `Document.status`: `processing`, `indexed`, `failed`

Also update Pydantic schemas to use `Literal[...]` or enums so bad values fail before hitting the database.

Suggested tests:

- Invalid role/status/type inserts should fail.
- API requests with invalid role/status/type should return validation errors.

## Problem 5: Timestamp Columns Mix Naive Database Columns With Timezone-Aware Python Values

Evidence:

- Models use `DateTime` without `timezone=True`.
- Runtime code sets some values with `datetime.now(timezone.utc)`, for example `published_at`, `started_at`, and `completed_at`.
- Server defaults use `func.now()`, which may produce database-local or timezone-specific values depending on the database.

Why this is a problem:

- Naive and aware datetimes can compare incorrectly in Python.
- PostgreSQL and SQLite can behave differently.
- API responses may be inconsistent around timezone handling.

Proper fix:

Choose one convention.

Recommended convention:

```python
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    onupdate=func.now(),
)
published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

Apply this consistently to all model datetime columns.

Alternative:

- Store naive UTC everywhere and use `datetime.utcnow()` or a helper that strips timezone info.
- This is less explicit and easier to misuse.

Suggested tests:

- Persist and reload `published_at`, `started_at`, and `completed_at`; assert they use the chosen timezone convention.
- Ensure API serialization is stable.

## Problem 6: JSON Columns Are Not Mutation-Tracked

Evidence:

- Models use plain `JSON` columns for mutable dict/list data:
  - `KnowledgeBase.config`
  - `Document.metadata_`
  - `Document.atlas_document_ids`
  - `Execution.input_data`
  - `Execution.output_data`
  - `Execution.token_usage`
- SQLAlchemy does not automatically detect in-place mutations inside plain JSON values.

Why this is a problem:

- Code like `execution.token_usage["total"] = 10` may not be persisted unless the whole dict is reassigned or the field is manually marked modified.
- This creates subtle data-loss bugs.

Proper fix:

Use SQLAlchemy mutable wrappers for JSON columns that are mutated in place:

```python
from sqlalchemy.ext.mutable import MutableDict, MutableList

config: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), nullable=False, default=dict)
token_usage: Mapped[dict | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
atlas_document_ids: Mapped[list | None] = mapped_column(MutableList.as_mutable(JSON), nullable=True)
```

If the codebase always reassigns complete JSON objects, document that convention and avoid in-place mutations.

Suggested tests:

- Load a row, mutate a JSON dict/list in place, commit, reload, and assert the change persisted.

## Problem 7: Creator Foreign Keys Can Block User Deletion Or Lose Intended History

Evidence:

- `Workflow.created_by` references `users.id` without `ondelete`.
- `WorkflowVersion.created_by` references `users.id` without `ondelete`.
- `ApiKey.created_by` references `users.id` without `ondelete`.
- `AuditLog.user_id` already uses `ondelete="SET NULL"`, which is a better historical-record pattern.

Why this is a problem:

- Deleting a user who created workflows, versions, or API keys in another workspace may fail due to foreign key restrictions.
- If deletion should be restricted, this should be intentional and documented.
- If historical records should survive user deletion, these columns should allow null and use `SET NULL`.

Proper fix:

Decide per model:

- For historical records such as workflow versions and audit-like records, prefer nullable creator columns with `ondelete="SET NULL"`.
- For ownership-like records that should block deletion, keep non-null FKs and document the restriction.

Example:

```python
created_by: Mapped[str | None] = mapped_column(
    String(36),
    ForeignKey("users.id", ondelete="SET NULL"),
    nullable=True,
)
```

Suggested tests:

- Delete a user who created a workflow in a workspace they do not own.
- Assert the chosen behavior: either deletion is blocked with a clear error or creator references become `NULL`.

## Problem 8: Model Relationships Are Missing Some Useful Backrefs And Indexes

Evidence:

- `Execution` has `workspace_id`, but no `workspace = relationship(...)`.
- `Workflow.created_by`, `WorkflowVersion.created_by`, `ApiKey.created_by`, and `AuditLog.user_id` have no user relationships.
- `ApiKey.workspace_id` is not indexed, while most workspace-scoped tables are.

Why this is a problem:

- Missing relationships make common ORM queries harder and can encourage duplicate manual joins.
- Missing workspace indexes can slow workspace-scoped API key lookups as data grows.

Proper fix:

Add relationships only where the application actually needs ORM navigation. At minimum, add the obvious workspace index:

```python
workspace_id: Mapped[str] = mapped_column(
    String(36),
    ForeignKey("workspaces.id", ondelete="CASCADE"),
    nullable=False,
    index=True,
)
```

Optional relationships:

```python
class Execution(Base):
    workspace = relationship("Workspace")

class ApiKey(Base):
    creator = relationship("User")

class AuditLog(Base):
    user = relationship("User")
```

Suggested tests/checks:

- Alembic autogenerate should include the new index.
- Existing API key queries should use the index for workspace filtering.

## Problem 9: Alembic Has No Current Version File To Materialize These Models

Evidence:

- `backend/alembic/versions` has no migration files in the current working tree.
- `git status` shows a deleted initial migration: `backend/alembic/versions/65d6f9f49fdc_initial.py`.
- Models have changed recently, especially `workflow.py`, `execution.py`, and `knowledge.py`.

Why this is a problem:

- The database schema cannot be reliably recreated or upgraded from model definitions.
- Other agents or environments may run against stale tables.
- Model fixes will not reach the database without migrations.

Proper fix:

After fixing the model definitions:

```bash
cd backend
alembic revision --autogenerate -m "fix model schema contracts"
alembic upgrade head
```

Review the generated migration carefully, especially:

- `workflow.mongo_flow_id`
- `workflow_versions.mongo_flow_id`
- uniqueness on `(workflow_id, version)`
- status/type/role check constraints
- JSON type changes
- timezone changes
- nullable creator foreign keys

Suggested verification:

- Run migrations from an empty database.
- Run migrations against an existing development database if one exists.
- Import all models and inspect `Base.metadata.tables`.

## Problem 10: Minor Cleanup Issues

Evidence:

- `backend/app/models/workflow.py` imports `JSON` but does not use it.
- `backend/app/models/api_key.py` imports `INET` but does not use it.
- Comments such as `# Unique constraint on workflow_id + version` are currently inaccurate.

Why this is a problem:

- Stale imports and stale comments make the model layer harder to trust.
- They hide the difference between intended schema and actual schema.

Proper fix:

- Remove unused imports.
- Update comments to describe the actual model behavior.
- Prefer database constraints over comments for important rules.

Suggested checks:

```bash
python -m py_compile backend/app/models/*.py
```

Use a linter such as Ruff later if the project adds one.

## Recommended Implementation Order

1. Fix the workflow storage contract first: either fully Mongo-backed flow blobs or fully SQL-backed JSON.
2. Fix `WorkflowVersion` so version snapshots use the same storage strategy and enforce uniqueness.
3. Replace PostgreSQL-only `JSONB` with portable `JSON`, unless the project commits to Postgres.
4. Add model-level constraints for roles, statuses, trigger types, and knowledge/document types.
5. Standardize datetime timezone handling.
6. Add mutable JSON tracking where in-place JSON mutation is expected.
7. Decide `created_by` deletion behavior and update foreign keys accordingly.
8. Add useful indexes/relationships.
9. Generate and review Alembic migrations.
10. Add focused model/router tests.

## Verification Commands

Run these in a compatible backend environment after implementing fixes:

```bash
python -m py_compile backend/app/models/*.py

cd backend
python - <<'PY'
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import sqlite
from app.database import Base
import app.models  # noqa
for table in Base.metadata.sorted_tables:
    str(CreateTable(table).compile(dialect=sqlite.dialect()))
print("sqlite model DDL compiles")
PY

alembic revision --autogenerate -m "verify model schema changes"
alembic upgrade head
pytest tests -q
```

## Notes For The CLI Agent

- Do not edit unrelated frontend files.
- Preserve user-owned uncommitted changes unless a model fix must build on them.
- Keep the SQL models, Pydantic schemas, routers, executor, and migrations synchronized.
- Add tests that fail on the current broken workflow/model contract and pass after the fix.
- If MongoDB is required in tests, mock `BlobService` rather than depending on a live MongoDB instance.
