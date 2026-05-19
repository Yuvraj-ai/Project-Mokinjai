# Backend Routers Code Problems And Fix Plan

Scope reviewed: `backend/app/routers`.

This file is written as an implementation handoff for a CLI coding agent. Fix the problems in priority order, keep changes scoped, and add tests for the route behavior.

## Current Files

- `backend/app/routers/__init__.py`
- `backend/app/routers/auth.py`
- `backend/app/routers/executions.py`
- `backend/app/routers/knowledge.py`
- `backend/app/routers/users.py`
- `backend/app/routers/workflows.py`
- `backend/app/routers/workspaces.py`

## Problem 1: Router Package Does Not Compile

Evidence:

- `python -m py_compile backend/app/routers/*.py` fails.
- `backend/app/routers/executions.py` has duplicated/corrupted lines at the end:
  - line 149: `  return {"success": True}`
  - line 150: `ecution.status = "cancelled"`
- `backend/app/routers/workflows.py` has duplicated/corrupted lines at the end:
  - line 189: `workflow is None:`
  - line 197: `ne_or_none()`
- `backend/app/schemas/execution.py` also has syntax corruption at lines 47-48. Even though this is outside `routers`, `executions.py` imports `ExecutionResponse` and `ExecutionListResponse`, so the router import path is blocked until the schema is fixed too.

Why this is a problem:

- The API cannot start while these syntax errors exist.
- Any test suite that imports `app.main` or `app.routers.executions` will fail immediately.

Proper fix:

1. Remove the corrupted duplicate tail from `executions.py` so `cancel_execution()` ends at:

   ```python
   execution.status = "cancelled"
   execution.completed_at = datetime.now(timezone.utc)
   await db.commit()
   return {"success": True}
   ```

2. Remove the corrupted duplicate tail from `workflows.py` so `publish_workflow()` ends at:

   ```python
   workflow.status = "published"
   workflow.published_at = datetime.now(timezone.utc)
   await db.commit()
   await db.refresh(workflow)
   return workflow
   ```

3. Fix `backend/app/schemas/execution.py` by removing the stray lines:

   ```python
   nResponse]
       total: int
   ```

4. Add the missing `Decimal` import in `backend/app/schemas/execution.py`:

   ```python
   from decimal import Decimal
   ```

Suggested verification:

```bash
python -m py_compile backend/app/routers/*.py backend/app/schemas/execution.py
```

## Problem 2: Workflow Routes Still Use Removed SQL `flow_definition` Fields

Evidence:

- `backend/app/models/workflow.py` has `mongo_flow_id`, but no `flow_definition` column.
- `backend/app/routers/workflows.py` creates `Workflow(flow_definition=...)`.
- `backend/app/routers/workflows.py` assigns `workflow.flow_definition = ...`.
- `backend/app/routers/workflows.py` creates `WorkflowVersion(flow_definition=...)`, but `WorkflowVersion` has `mongo_flow_id`, not `flow_definition`.
- `backend/app/routers/executions.py` checks `workflow.flow_definition.get("nodes")`.

Why this is a problem:

- Workflow create, update, version snapshot, and execution will fail at runtime with invalid constructor arguments or `AttributeError`.
- The router layer and model layer disagree about where flow JSON is stored.

Proper fix:

Use the Mongo blob strategy already implied by the model and `BlobService`.

Create workflow:

```python
flow_data = request.flow_definition.model_dump()
mongo_flow_id = await BlobService.save_blob(flow_data)
workflow = Workflow(
    workspace_id=workspace_id,
    name=request.name,
    description=request.description,
    mongo_flow_id=mongo_flow_id,
    created_by=current_user.id,
)
```

Update workflow:

```python
if request.flow_definition is not None:
    flow_data = request.flow_definition.model_dump()
    if workflow.mongo_flow_id:
        await BlobService.update_blob(workflow.mongo_flow_id, flow_data)
    else:
        workflow.mongo_flow_id = await BlobService.save_blob(flow_data)

    version_flow_id = await BlobService.save_blob(flow_data)
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

Execution precheck:

```python
flow_def = await BlobService.get_blob(workflow.mongo_flow_id)
if not flow_def or not flow_def.get("nodes"):
    raise BadRequestException("Workflow has no nodes to execute")
```

Suggested tests:

- `POST /workflows` saves a blob and persists `mongo_flow_id`.
- `PUT /workflows/{workflow_id}` updates the active blob and creates a version snapshot with `mongo_flow_id`.
- `POST /workflows/{workflow_id}/execute` rejects empty flow blobs with `400`, not `AttributeError`.

## Problem 3: Workflow Create Can Leave Orphan Mongo Blobs If SQL Commit Fails

Evidence:

- The proper Mongo-backed create flow must save a blob before SQL commit so the `mongo_flow_id` can be stored on `Workflow`.
- If SQL commit fails after `BlobService.save_blob()`, the Mongo blob remains orphaned.

Why this is a problem:

- Failed API requests can leak blob records.
- Over time, storage can fill with unreachable flow definitions.

Proper fix:

Wrap SQL commit and clean up the blob on failure:

```python
mongo_flow_id = await BlobService.save_blob(flow_data)
try:
    workflow = Workflow(..., mongo_flow_id=mongo_flow_id)
    db.add(workflow)
    await db.commit()
except Exception:
    await db.rollback()
    await BlobService.delete_blob(mongo_flow_id)
    raise
```

Suggested tests:

- Mock `db.commit()` to fail and assert `BlobService.delete_blob()` is called.

## Problem 4: Workflow Delete Does Not Delete Associated Mongo Flow Blobs

Evidence:

- `delete_workflow()` deletes the SQL `Workflow` only.
- Current models store active flow JSON in `Workflow.mongo_flow_id`.
- Version snapshots also point at Mongo blobs through `WorkflowVersion.mongo_flow_id`.

Why this is a problem:

- Deleting a workflow leaves orphaned Mongo blobs.
- The database cascade only handles SQL rows, not external blob storage.

Proper fix:

Before deleting the workflow, collect active and version blob IDs, delete the SQL row, commit, then delete blobs. If blob deletion failure should not fail the user request, log it clearly.

```python
blob_ids = [workflow.mongo_flow_id, *(v.mongo_flow_id for v in workflow.versions)]
await db.delete(workflow)
await db.commit()
for blob_id in filter(None, blob_ids):
    await BlobService.delete_blob(blob_id)
```

If lazy loading relationships is unsafe in async SQLAlchemy, explicitly query `WorkflowVersion.mongo_flow_id`.

Suggested tests:

- Deleting a workflow calls `BlobService.delete_blob()` for the active flow blob and version blobs.

## Problem 5: Execution Routes Do Not Hydrate Execution Trace From MongoDB

Evidence:

- `Execution` stores `mongo_trace_id`.
- `ExecutionResponse` exposes `execution_trace`.
- `list_executions()` explicitly sets `execution_trace = None`.
- `get_execution()` returns the SQL model directly, so the response will not include the Mongo trace data.

Why this is a problem:

- Detailed execution view cannot return the trace even after the executor saved it.
- The API response schema advertises `execution_trace`, but the route does not populate it.

Proper fix:

Keep list responses lightweight, but hydrate trace in detail responses:

```python
from app.services.blob_service import BlobService

response = ExecutionResponse.model_validate(execution)
response.execution_trace = await BlobService.get_blob(execution.mongo_trace_id)
return response
```

Suggested tests:

- `GET /executions/{execution_id}` returns trace data when `mongo_trace_id` exists.
- `GET /executions` omits trace data to keep list responses small.

## Problem 6: Async Execution Dispatch Can Leave Records Stuck In `pending`

Evidence:

- `execute_workflow()` creates and commits an `Execution` with `status="pending"`.
- If `run_workflow_task.delay(execution.id)` raises because Redis/Celery is unavailable, the exception leaves the already-committed execution as `pending`.

Why this is a problem:

- Users see a pending execution that will never run.
- The API may return a 500 while still leaving a committed record.

Proper fix:

Handle dispatch failure explicitly:

```python
try:
    run_workflow_task.delay(execution.id)
except Exception as exc:
    execution.status = "failed"
    execution.error_message = f"Failed to enqueue execution: {exc}"
    execution.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(execution)
    raise BadRequestException("Failed to enqueue workflow execution")
```

Better long-term fix:

- Use an outbox table or background job state machine so SQL state and queue dispatch are coordinated.

Suggested tests:

- Mock `run_workflow_task.delay()` to raise and assert the execution is marked `failed`.

## Problem 7: Cancel Route Only Changes DB Status; It Does Not Stop Running Work

Evidence:

- `cancel_execution()` sets `execution.status = "cancelled"` and commits.
- It does not revoke Celery tasks.
- `WorkflowExecutor` does not check for cancellation between nodes.
- Synchronous executions cannot be interrupted by this endpoint.

Why this is a problem:

- A "cancelled" execution may continue running and later overwrite status to `completed` or `failed`.
- Users get misleading state.

Proper fix:

1. Add a cooperative cancellation check inside `WorkflowExecutor` before each node execution.
2. Store Celery task IDs on `Execution` if async cancellation should revoke queued/running tasks.
3. In `cancel_execution()`, reject cancellation only for terminal states, mark cancellation requested, and let the worker transition safely.

Minimum scoped fix:

```python
if execution.status in ("completed", "failed", "cancelled"):
    raise BadRequestException(...)
execution.status = "cancelled"
execution.completed_at = datetime.now(timezone.utc)
await db.commit()
```

Then update executor to stop if it reloads the execution and sees `cancelled`.

Suggested tests:

- Cancelling a pending execution marks it cancelled.
- Executor does not continue processing an execution that has been cancelled.
- A running async task cannot overwrite a cancelled terminal state.

## Problem 8: Member Role Input Allows Privilege Escalation

Evidence:

- `workspaces.py` lets any admin call `POST /{workspace_id}/members`.
- `MemberAdd.role` is an unrestricted string.
- The route stores `request.role` directly.
- An admin can add another user with `role="owner"` or any invalid role string.

Why this is a problem:

- Admins can create new owners even though owner-only operations exist.
- Invalid roles can break RBAC or silently produce denied/incorrect behavior.

Proper fix:

1. Restrict allowed roles in the schema with `Literal` or an enum.
2. Do not allow this route to create owners unless the current actor is owner.
3. Prefer separate owner-transfer logic for ownership changes.

Example:

```python
from typing import Literal

class MemberAdd(BaseModel):
    user_id: str
    role: Literal["admin", "editor", "viewer"] = "viewer"
```

If owners can add owners, return the current member from the dependency and check it:

```python
member: WorkspaceMember = Depends(require_workspace_role("admin"))
if request.role == "owner" and member.role != "owner":
    raise ForbiddenException("Only owners can add owners")
```

Suggested tests:

- Admin cannot add a member as owner.
- Invalid role returns validation error.
- Owner role transfer, if supported, has a dedicated test.

## Problem 9: Auth Registration And Member Add Have Race Conditions Around Unique Data

Evidence:

- `auth.register()` checks if email exists, then inserts the user.
- `workspaces.add_member()` checks if membership exists, then inserts.
- The database can still raise an integrity error if two requests race between check and commit.

Why this is a problem:

- Duplicate concurrent requests can produce uncaught `IntegrityError` and a 500 response.
- The intended user-facing errors are `Email already registered` and `User is already a member`.

Proper fix:

Catch `IntegrityError`, roll back, and return the appropriate API error:

```python
from sqlalchemy.exc import IntegrityError

try:
    db.add(user)
    await db.commit()
except IntegrityError:
    await db.rollback()
    raise BadRequestException("Email already registered")
```

Do the same for duplicate workspace membership.

Suggested tests:

- Mock or trigger duplicate email insert and assert `400`, not `500`.
- Mock or trigger duplicate workspace member insert and assert `400`, not `500`.

## Problem 10: Auth Refresh Leaks User Existence Details And Has No Token Rotation Guard

Evidence:

- `auth.refresh_token()` returns `UnauthorizedException("User not found")` when the refresh token subject no longer exists.
- It accepts any valid refresh token until expiry and returns a new refresh token every time.

Why this is a problem:

- `"User not found"` reveals account state.
- Without refresh-token identifiers, storage, rotation, or revocation, stolen refresh tokens remain reusable until expiry.

Proper fix:

Minimum scoped fix:

```python
if user is None:
    raise UnauthorizedException("Invalid refresh token")
```

Better fix:

- Add a `jti` claim to refresh tokens.
- Store refresh token records or hashes server-side.
- Rotate refresh tokens on use and revoke the old one.
- Revoke all refresh tokens for a user on password reset or account deletion.

Suggested tests:

- Refresh token for a deleted user returns generic `401`.
- Reusing a rotated refresh token fails after token storage is implemented.

## Problem 11: Status And Type Query/Input Values Are Not Validated

Evidence:

- `list_workflows(status: str | None = None)` accepts any status string.
- `list_executions(status: str | None = None)` accepts any status string.
- `KnowledgeBaseCreate.type` is a free string.
- `MemberAdd.role` is a free string.

Why this is a problem:

- Typoed filters silently return empty results.
- Bad type/role values can be stored.
- API behavior becomes harder for clients to reason about.

Proper fix:

Use enums or `Literal` values in schemas and route query parameters.

Example:

```python
from typing import Literal

WorkflowStatus = Literal["draft", "published", "archived"]
ExecutionStatus = Literal["pending", "running", "completed", "failed", "cancelled"]

async def list_workflows(status: WorkflowStatus | None = None, ...):
    ...
```

Suggested tests:

- Invalid status query returns `422`.
- Invalid knowledge base type returns `422`.
- Invalid member role returns `422`.

## Problem 12: Publish Route Does Not Validate Workflow Readiness

Evidence:

- `publish_workflow()` sets `workflow.status = "published"` without validating the workflow has a stored flow definition or nodes.
- With Mongo-backed flow storage, `mongo_flow_id` may be missing or point to an empty flow.

Why this is a problem:

- Users can publish workflows that cannot execute.
- Published status becomes unreliable.

Proper fix:

Before publishing, load and validate the flow:

```python
flow_def = await BlobService.get_blob(workflow.mongo_flow_id)
if not flow_def or not flow_def.get("nodes"):
    raise BadRequestException("Cannot publish a workflow with no nodes")
```

Also consider validating DAG structure with `DAGBuilder` if publishing should guarantee executability.

Suggested tests:

- Publishing a workflow without nodes returns `400`.
- Publishing a valid workflow sets status and `published_at`.

## Problem 13: `users.py` Is Dead Placeholder Router

Evidence:

- `backend/app/routers/users.py` only declares an empty `APIRouter`.
- `backend/app/main.py` does not include `users.router`.
- User creation and `/me` live in `auth.py`.

Why this is a problem:

- It creates ambiguity about where user endpoints belong.
- Future agents may add endpoints to `users.py` and assume they are reachable.

Proper fix:

Pick one:

- Delete `users.py` if there are no user routes planned.
- Or include it in `main.py` with a clear prefix and move user-management endpoints there.

Suggested verification:

- If kept, route listing should show the users routes.
- If deleted, no imports should reference it.

## Problem 14: Routes Commit Without Rollback On Exceptions

Evidence:

- Multiple routes call `await db.commit()` directly.
- `get_db()` closes sessions but does not roll back failed transactions.
- Routes that add external side effects, such as Mongo blobs or queued Celery tasks, need explicit rollback/cleanup.

Why this is a problem:

- A failed commit can leave the session in an unusable state for the remainder of request handling.
- External side effects can remain even when SQL changes fail.

Proper fix:

For each route that writes:

```python
try:
    await db.commit()
except Exception:
    await db.rollback()
    raise
```

For routes with external side effects, add compensating cleanup as described in the workflow blob and Celery sections.

Suggested tests:

- Simulate commit failure and assert rollback is called.
- Simulate SQL failure after blob creation and assert blob cleanup is called.

## Problem 15: Empty Updates Are Accepted As Successful Changes

Evidence:

- `update_workspace()` succeeds when `WorkspaceUpdate(name=None)` has no actual change.
- `update_workflow()` succeeds when all update fields are absent or null.

Why this is a problem:

- Clients can believe an update occurred when nothing changed.
- It can hide bad frontend payloads.

Proper fix:

Use Pydantic's field tracking and reject empty update payloads:

```python
if not request.model_fields_set:
    raise BadRequestException("No update fields provided")
```

For nullable fields such as `description`, distinguish "omitted" from "set to null":

```python
if "description" in request.model_fields_set:
    workflow.description = request.description
```

Suggested tests:

- Empty workspace update returns `400`.
- Workflow update can intentionally clear `description` to `null`.

## Recommended Implementation Order

1. Fix syntax corruption in `executions.py`, `workflows.py`, and `schemas/execution.py`.
2. Make workflow create/update/execute/publish agree with the model's Mongo-backed flow storage.
3. Hydrate execution trace in detail responses.
4. Add dispatch failure handling for async execution.
5. Make cancellation semantics honest and cooperative.
6. Lock down workspace member roles and status/type filters.
7. Add `IntegrityError` handling and rollback around writes.
8. Clean up dead `users.py` or wire it intentionally.
9. Add tests for the fixed route contracts.

## Verification Commands

Run these after implementing fixes:

```bash
python -m py_compile backend/app/routers/*.py backend/app/schemas/*.py
python -c "from app.main import app; print(len(app.routes))"
pytest backend/tests -q
```

If the backend package is executed from inside `backend`, use:

```bash
cd backend
python -c "from app.main import app; print(len(app.routes))"
pytest tests -q
```

## Notes For The CLI Agent

- Do not edit unrelated frontend files.
- Preserve existing user-owned uncommitted changes unless a router fix must build on them.
- Keep routers, schemas, models, `BlobService`, and `WorkflowExecutor` synchronized.
- Mock `BlobService`, Celery dispatch, and workflow execution in route tests; do not require live MongoDB or Redis for unit tests.
- Prefer focused route tests that reproduce each current failure before applying the fix.
