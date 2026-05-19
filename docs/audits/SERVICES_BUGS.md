# Services Bug Report — `backend/app/` (services, routers, middleware, utils, workers, websocket)

> **Purpose:** Read by a CLI agent. Fix each issue in order. Do NOT skip any issue.

---

## ISSUE 1 — `routers/executions.py`: Duplicate/garbage code at end of file (SYNTAX BUG — FILE WON'T PARSE)

**File:** `backend/app/routers/executions.py`
**Lines:** 148–153

**Problem:**
Lines 148–153 are a garbled duplicate of the `cancel_execution` handler body. Python will fail to parse this file entirely, meaning ALL execution endpoints return 500 on import.

```python
# Current broken lines 148–153:
    return {\"success\": True}
  return {\"success\": True}          # <-- bad indentation, duplicate
ecution.status = \"cancelled\"        # <-- truncated identifier, SyntaxError
    execution.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {\"success\": True}
```

**Fix:** Delete lines 149–153. The file should end cleanly after line 148:

```python
    execution.status = "cancelled"
    execution.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"success": True}
```

---

## ISSUE 2 — `routers/workflows.py`: Duplicate/garbage code at end of `publish_workflow` (SYNTAX BUG)

**File:** `backend/app/routers/workflows.py`
**Lines:** 189–205

**Problem:**
Lines 189–205 are a garbled triple-duplication of the `publish_workflow` handler body:

```python
workflow is None:           # truncated — SyntaxError
        raise NotFoundException(\"Workflow\")
    workflow.status = \"published\"
    ...
ne_or_none()                # truncated — SyntaxError
    if workflow is None:
    ...
```

**Fix:** Delete lines 189–205 entirely. The function should end at line 188:

```python
    workflow.status = "published"
    workflow.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(workflow)
    return workflow
```

---

## ISSUE 3 — `schemas/execution.py`: `Decimal` used but never imported, and duplicate class definition

**File:** `backend/app/schemas/execution.py`
**Lines:** 36, 47–48

**Problem:**
1. `Decimal` is used at line 36 (`cost_usd: Decimal | None = None`) but is never imported — causes `NameError` at startup.
2. Lines 47–48 are a garbled duplicate of `ExecutionListResponse`:
```
nResponse]      # truncated garbage
    total: int
```

**Fix:**
Add import at top of file:
```python
from decimal import Decimal
```
Delete lines 47–48 (the garbled duplicate). The class should end cleanly at line 46:
```python
class ExecutionListResponse(BaseModel):
    executions: list[ExecutionResponse]
    total: int
```

---

## ISSUE 4 — `routers/executions.py`: `workflow.flow_definition` accessed directly but flow is stored in MongoDB

**File:** `backend/app/routers/executions.py`
**Lines:** 38–39

**Problem:**
```python
if not workflow.flow_definition.get("nodes"):
    raise BadRequestException("Workflow has no nodes to execute")
```
According to `models/workflow.py`, the `Workflow` model has `mongo_flow_id` (a MongoDB ObjectId reference) — the actual flow definition lives in MongoDB, not in a `flow_definition` column on the SQL model. Calling `.flow_definition` will raise `AttributeError` since no such column exists on the `Workflow` SQLAlchemy model.

**Fix:** Either remove the pre-execution validation (the executor already validates via `DAGBuilder.validate()`), or fetch from MongoDB first:
```python
# Option A — remove the premature check (recommended, executor handles it):
# Delete lines 38-39

# Option B — validate after fetching:
from app.services.blob_service import BlobService
flow_def = await BlobService.get_blob(workflow.mongo_flow_id)
if not flow_def or not flow_def.get("nodes"):
    raise BadRequestException("Workflow has no nodes to execute")
```

---

## ISSUE 5 — `routers/workflows.py`: `create_workflow` stores flow in SQL column but model uses MongoDB

**File:** `backend/app/routers/workflows.py`
**Lines:** 31–41

**Problem:**
```python
workflow = Workflow(
    ...
    flow_definition=request.flow_definition.model_dump(),   # no such SQL column
    ...
)
```
The `Workflow` SQL model does NOT have a `flow_definition` column — it has `mongo_flow_id`. The actual flow definition must be saved to MongoDB via `BlobService.save_blob()` first, and only the returned ID stored in `mongo_flow_id`.

**Fix:**
```python
@router.post("", response_model=WorkflowResponse)
async def create_workflow(...):
    flow_dict = request.flow_definition.model_dump()
    mongo_id = await BlobService.save_blob(flow_dict)   # save to MongoDB

    workflow = Workflow(
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        mongo_flow_id=mongo_id,                          # store reference
        created_by=current_user.id,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow
```

---

## ISSUE 6 — `routers/workflows.py`: `update_workflow` stores flow in `workflow.flow_definition` instead of updating MongoDB blob

**File:** `backend/app/routers/workflows.py`
**Lines:** 127–138

**Problem:**
Same as Issue 5. The update handler sets `workflow.flow_definition = ...` (non-existent SQL column) and also passes `workflow.flow_definition` (which is `None`) to `WorkflowVersion.flow_definition` — another non-existent column on `WorkflowVersion` which has `mongo_flow_id`.

**Fix:**
```python
if request.flow_definition is not None:
    flow_dict = request.flow_definition.model_dump()

    if workflow.mongo_flow_id:
        await BlobService.update_blob(workflow.mongo_flow_id, flow_dict)
    else:
        workflow.mongo_flow_id = await BlobService.save_blob(flow_dict)

    workflow.version += 1

    # Save version snapshot to MongoDB too
    version_mongo_id = await BlobService.save_blob(flow_dict)
    version = WorkflowVersion(
        workflow_id=workflow.id,
        version=workflow.version,
        mongo_flow_id=version_mongo_id,
        created_by=current_user.id,
    )
    db.add(version)
```

---

## ISSUE 7 — `routers/workflows.py`: `delete_workflow` does not delete the MongoDB blob (data leak)

**File:** `backend/app/routers/workflows.py`
**Lines:** 162–163**

**Problem:**
`await db.delete(workflow)` removes the SQL row but the associated MongoDB document (`workflow.mongo_flow_id`) is never deleted. Over time this leaks orphaned blobs in MongoDB with no cleanup path.

**Fix:**
```python
if workflow.mongo_flow_id:
    await BlobService.delete_blob(workflow.mongo_flow_id)
await db.delete(workflow)
await db.commit()
```

---

## ISSUE 8 — `services/blob_service.py`: `get_blob` raises `bson.errors.InvalidId` on malformed IDs

**File:** `backend/app/services/blob_service.py`
**Lines:** 22–24

**Problem:**
```python
doc = await db[cls.collection_name].find_one({"_id": ObjectId(blob_id)})
```
`ObjectId(blob_id)` raises `bson.errors.InvalidId` if `blob_id` is not a valid 24-hex-char string. This is unhandled and will surface as an unformatted 500 error to the client.

**Fix:**
```python
from bson.errors import InvalidId

@classmethod
async def get_blob(cls, blob_id: str) -> Optional[Any]:
    if not blob_id:
        return None
    try:
        oid = ObjectId(blob_id)
    except InvalidId:
        return None   # or raise NotFoundException
    db = await get_mongo_db()
    doc = await db[cls.collection_name].find_one({"_id": oid})
    return doc["data"] if doc else None
```
Apply the same guard to `update_blob` and `delete_blob`.

---

## ISSUE 9 — `utils/mongo.py`: Module-level `get_settings()` call at import time causes startup failures

**File:** `backend/app/utils/mongo.py`
**Line:** 4

**Problem:**
```python
settings = get_settings()   # called at module import time
```
If `get_settings()` raises (e.g., missing env vars), the entire application fails to import `mongo.py`, which cascades into import errors across every module that uses `BlobService`. This also means the cached settings object is created before any `.env` file is loaded by the test harness.

**Fix:** Lazy-load settings inside the class method:
```python
class MongoManager:
    client: AsyncIOMotorClient = None

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        if cls.client is None:
            from app.config import get_settings
            settings = get_settings()
            url = settings.MONGO_URL or "mongodb://localhost:27017"
            cls.client = AsyncIOMotorClient(url)
        return cls.client

    @classmethod
    def get_db(cls):
        from app.config import get_settings
        return cls.get_client()[get_settings().MONGO_DB_NAME]
```

---

## ISSUE 10 — `utils/security.py`: Module-level `get_settings()` call — same startup risk

**File:** `backend/app/utils/security.py`
**Line:** 6

**Problem:** Same as Issue 9. `settings = get_settings()` at module level means JWT secrets are baked in at import time, preventing test overrides via env vars.

**Fix:** Call `get_settings()` inside each function:
```python
def create_access_token(data: dict) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
```
Apply same pattern to `create_refresh_token` and `decode_token`.

---

## ISSUE 11 — `utils/security.py`: `decode_token` silently returns `None` on ALL JWT errors

**File:** `backend/app/utils/security.py`
**Lines:** 31–36

**Problem:**
```python
except JWTError:
    return None
```
`JWTError` catches both expired tokens AND tampered/invalid tokens. The caller cannot distinguish between "token expired" (show re-login UI) vs "token was forged" (security alert). Also, a network/library bug that raises `JWTError` accidentally would be silently swallowed.

**Fix:** Re-raise or distinguish:
```python
from jose import ExpiredSignatureError, JWTError

def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except ExpiredSignatureError:
        return None   # expired — caller can check and prompt re-login
    except JWTError:
        return None   # invalid signature or malformed
```
At minimum, log the error type for observability.

---

## ISSUE 12 — `routers/auth.py`: Refresh token endpoint issues a new refresh token on every call (token rotation without revocation)

**File:** `backend/app/routers/auth.py`
**Lines:** 54–71

**Problem:**
The `/refresh` endpoint issues a **new** refresh token every time. Without a token revocation store (e.g., Redis blacklist or DB table), old refresh tokens remain valid indefinitely. A stolen refresh token can be used forever.

**Fix:** Implement refresh token rotation with revocation. At minimum, store issued refresh token JTIs in Redis/DB and invalidate the old one when a new one is issued:
```python
# After validating old token, blacklist its jti:
jti = payload.get("jti")
if jti:
    await redis.setex(f"revoked:{jti}", REFRESH_TOKEN_EXPIRE_SECONDS, "1")

# When decoding, check blacklist:
jti = payload.get("jti")
if jti and await redis.get(f"revoked:{jti}"):
    raise UnauthorizedException("Token has been revoked")
```

---

## ISSUE 13 — `routers/auth.py`: No rate limiting on `/login` — brute-force vulnerability

**File:** `backend/app/routers/auth.py`
**Lines:** 39–51

**Problem:**
The login endpoint has no rate limiting. An attacker can attempt unlimited password guesses without any throttle or lockout.

**Fix:** Add a `slowapi` or `fastapi-limiter` rate limit decorator:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    ...
```

---

## ISSUE 14 — `middleware/rbac.py`: Returns `NotFoundException("Workspace")` when user is not a member — leaks workspace existence

**File:** `backend/app/middleware/rbac.py`
**Lines:** 27–28

**Problem:**
```python
if member is None:
    raise NotFoundException("Workspace")
```
Returning 404 when a workspace exists but the user isn't a member tells the attacker that the workspace ID is valid. The correct response is `403 Forbidden` (don't reveal whether the resource exists).

**Fix:**
```python
if member is None:
    raise ForbiddenException("You do not have access to this workspace")
```

---

## ISSUE 15 — `middleware/rbac.py`: Unknown roles resolve to level `0` — silently grants no access instead of erroring

**File:** `backend/app/middleware/rbac.py`
**Lines:** 30–33

**Problem:**
```python
min_level = ROLE_HIERARCHY.get(min_role, 0)
user_level = ROLE_HIERARCHY.get(member.role, 0)
```
If a user has an unrecognized role (e.g., a DB corruption or future role not yet added to `ROLE_HIERARCHY`), `user_level` becomes `0`, which is below every real role — so access is denied silently. Worse, if `min_role` is typo'd in a route decorator, `min_level` becomes `0`, granting all users access unexpectedly.

**Fix:** Raise on unknown roles:
```python
min_level = ROLE_HIERARCHY.get(min_role)
if min_level is None:
    raise ValueError(f"Unknown required role: {min_role}")

user_level = ROLE_HIERARCHY.get(member.role, 0)
```

---

## ISSUE 16 — `workers/execution_worker.py`: Celery task does not handle or retry on async exceptions

**File:** `backend/app/workers/execution_worker.py`
**Lines:** 7–15

**Problem:**
```python
@celery_app.task(name="run_workflow", bind=True, max_retries=3)
def run_workflow_task(self, execution_id: str):
    loop = asyncio.new_event_loop()
    ...
    try:
        loop.run_until_complete(_execute(execution_id))
    finally:
        loop.close()
```
1. `max_retries=3` is declared but `self.retry(exc=e)` is never called — exceptions just propagate and the task fails permanently on first error.
2. When `_execute` raises, the `Execution` record in the DB may remain stuck in `"running"` status forever (the executor's own except block handles DB cleanup, but if the DB session itself fails, no cleanup occurs).

**Fix:**
```python
@celery_app.task(name="run_workflow", bind=True, max_retries=3, default_retry_delay=10)
def run_workflow_task(self, execution_id: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_execute(execution_id))
    except Exception as exc:
        loop.close()
        raise self.retry(exc=exc)
    finally:
        if not loop.is_closed():
            loop.close()
```

---

## ISSUE 17 — `websocket/execution_ws.py`: Auth is optional — unauthenticated clients can connect freely

**File:** `backend/app/websocket/execution_ws.py`
**Lines:** 40–47

**Problem:**
```python
token = websocket.query_params.get("token")
if token:                    # only validates IF token is provided
    payload = decode_token(token)
    if payload is None:
        await websocket.close(code=4001)
        return
await manager.connect(websocket, execution_id)   # always connects
```
If no `token` query param is provided, the connection is accepted unconditionally. Any unauthenticated user can subscribe to any execution's WebSocket feed.

**Fix:** Make auth mandatory:
```python
token = websocket.query_params.get("token")
if not token:
    await websocket.close(code=4001)
    return
payload = decode_token(token)
if payload is None or payload.get("type") != "access":
    await websocket.close(code=4001)
    return
```

---

## ISSUE 18 — `websocket/execution_ws.py`: `send_event` silently swallows ALL exceptions on send

**File:** `backend/app/websocket/execution_ws.py`
**Lines:** 28–31

**Problem:**
```python
try:
    await connection.send_text(message)
except Exception:
    pass   # silently drops failed sends
```
Dead/stale connections are never cleaned up from `active_connections`. Over time, `active_connections[execution_id]` accumulates closed sockets that are retried on every broadcast, wasting resources.

**Fix:** Remove dead connections on send failure:
```python
async def send_event(self, execution_id: str, event: dict):
    if execution_id not in self.active_connections:
        return
    message = json.dumps(event)
    dead = []
    for connection in self.active_connections[execution_id]:
        try:
            await connection.send_text(message)
        except Exception:
            dead.append(connection)
    for conn in dead:
        self.disconnect(conn, execution_id)
```

---

## ISSUE 19 — `models/workflow.py`: `WorkflowVersion.__table_args__` is wrong — missing `UniqueConstraint`

**File:** `backend/app/models/workflow.py`
**Lines:** 45–48

**Problem:**
```python
__table_args__ = (
    {"sqlite_autoincrement": True},   # wrong — this is a dict, not a tuple of constraints
)
```
A comment above says "Unique constraint on workflow_id + version" but the actual constraint is never defined. The `{"sqlite_autoincrement": True}` dict is the table-level kwargs arg that SQLAlchemy expects as the **last element** of a tuple of constraints. Using it alone with no constraints is both incorrect (the option has no effect on a non-integer PK) and misleading.

**Fix:**
```python
from sqlalchemy import UniqueConstraint

__table_args__ = (
    UniqueConstraint("workflow_id", "version", name="uq_workflow_version"),
)
```

---

## ISSUE 20 — `config.py`: Hardcoded MongoDB URL with placeholder password in default value

**File:** `backend/app/config.py`
**Line:** 10

**Problem:**
```python
MONGO_URL: str = "mongodb+srv://norton0610nexus_db_user:<db_password>@mokinjaicluster..."
```
The default value contains a literal `<db_password>` placeholder. If `.env` is missing or `MONGO_URL` is not overridden, Motor will attempt to connect to Atlas using the string `<db_password>` as the password, failing with an auth error at runtime. Worse, the username and cluster name are committed to source control.

**Fix:** Use an empty default and require it from the environment:
```python
MONGO_URL: str = ""   # Must be set in .env
```
And update `mongo.py` to handle an empty `MONGO_URL` gracefully:
```python
url = settings.MONGO_URL
if not url:
    raise RuntimeError("MONGO_URL is not configured. Set it in your .env file.")
```

---

## Summary Table

| # | File | Severity | Category | One-Line Description |
|---|------|----------|----------|----------------------|
| 1 | routers/executions.py | **Critical** | Syntax | Garbled duplicate code — file won't parse |
| 2 | routers/workflows.py | **Critical** | Syntax | Garbled triple-duplicate in publish handler |
| 3 | schemas/execution.py | **Critical** | Syntax/Import | `Decimal` not imported + duplicate class fragment |
| 4 | routers/executions.py | High | Logic | `workflow.flow_definition` accessed — column doesn't exist |
| 5 | routers/workflows.py | High | Logic | `create_workflow` writes to non-existent SQL column |
| 6 | routers/workflows.py | High | Logic | `update_workflow` writes flow to SQL instead of MongoDB |
| 7 | routers/workflows.py | Medium | Data Leak | Delete workflow leaves orphaned MongoDB blob |
| 8 | services/blob_service.py | High | Bug | Unhandled `InvalidId` exception on bad ObjectId |
| 9 | utils/mongo.py | Medium | Startup | Module-level `get_settings()` causes import-time failures |
| 10 | utils/security.py | Medium | Startup | Module-level `get_settings()` bakes in JWT secret at import |
| 11 | utils/security.py | Medium | Security | `decode_token` swallows all JWT errors silently |
| 12 | routers/auth.py | High | Security | Refresh tokens never revoked — stolen tokens live forever |
| 13 | routers/auth.py | High | Security | No rate limiting on `/login` — brute-force possible |
| 14 | middleware/rbac.py | Medium | Security | 404 on non-member leaks workspace existence |
| 15 | middleware/rbac.py | Medium | Bug | Unknown roles silently resolve to level 0 |
| 16 | workers/execution_worker.py | High | Bug | Celery retries declared but never triggered |
| 17 | websocket/execution_ws.py | High | Security | Auth is optional — unauthenticated WS connections accepted |
| 18 | websocket/execution_ws.py | Medium | Resource Leak | Dead WS connections never removed from pool |
| 19 | models/workflow.py | Medium | Data Integrity | `UniqueConstraint` on version missing — duplicates possible |
| 20 | config.py | High | Security | Hardcoded MongoDB URL with plaintext username in source |
