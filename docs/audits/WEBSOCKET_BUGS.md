# WebSocket Bug Report — `backend/app/websocket/`

> **Purpose:** Read by a CLI agent. Fix each issue in order. Do NOT skip any issue.
> Scope covers `execution_ws.py` and its integration point in `main.py`.

---

## ISSUE 1 — Authentication is optional — unauthenticated clients can connect to any execution stream

**File:** `backend/app/websocket/execution_ws.py`
**Lines:** 40–47

**Problem:**
```python
token = websocket.query_params.get("token")
if token:                    # only validates IF token is present
    payload = decode_token(token)
    if payload is None:
        await websocket.close(code=4001)
        return

await manager.connect(websocket, execution_id)   # always runs
```
If no `token` query parameter is provided, the entire auth block is skipped and the connection is accepted unconditionally. Any unauthenticated user who knows (or guesses) an `execution_id` can subscribe to its real-time event stream, potentially leaking input data, output data, and execution traces.

**Fix:** Make the token mandatory and validate its type:
```python
async def execution_websocket(websocket: WebSocket, execution_id: str):
    """WebSocket endpoint for real-time execution updates."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing auth token")
        return

    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await manager.connect(websocket, execution_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, execution_id)
```

---

## ISSUE 2 — No authorization check — authenticated users can watch ANY execution, even in other workspaces

**File:** `backend/app/websocket/execution_ws.py`
**Lines:** 37–54

**Problem:**
Even with auth fixed (Issue 1), there is no workspace membership or ownership check. A valid user from Workspace A can connect to an execution belonging to Workspace B by simply passing the `execution_id`. The HTTP API correctly checks `workspace_id` membership via RBAC middleware, but the WebSocket endpoint bypasses all of that.

**Fix:** After token validation, verify the user has access to the execution's workspace:
```python
from app.database import async_session
from sqlalchemy import select
from app.models.execution import Execution
from app.models.workspace import WorkspaceMember

async def execution_websocket(websocket: WebSocket, execution_id: str):
    # ... (token validation from Issue 1) ...

    user_id = payload.get("sub")

    # Verify user has access to this execution's workspace
    async with async_session() as db:
        result = await db.execute(
            select(Execution).where(Execution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        if execution is None:
            await websocket.close(code=4004, reason="Execution not found")
            return

        result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == execution.workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            await websocket.close(code=4003, reason="Access denied")
            return

    await manager.connect(websocket, execution_id)
    # ...
```

---

## ISSUE 3 — `send_event` is never called — WebSocket connections receive no events

**File:** `backend/app/websocket/execution_ws.py` (line 24) and `backend/app/engine/executor.py`

**Problem:**
The `ConnectionManager.send_event()` method exists but is **never called from anywhere** in the codebase. A codebase-wide grep for `send_event` and `manager.send_event` confirms zero callers outside the definition itself. This means:
- Clients connect to the WebSocket and sit in a dead `while True: await websocket.receive_text()` loop
- The executor runs workflows but never pushes node-status updates to connected clients
- The entire WebSocket feature is non-functional

**Fix:** Import and call `manager.send_event()` from the executor during node execution. Add event broadcasts at key points in `backend/app/engine/executor.py`:

```python
# At the top of executor.py, add:
from app.websocket.execution_ws import manager as ws_manager

# Inside the node execution loop (after context.set_output):
await ws_manager.send_event(execution_id, {
    "type": "node_completed",
    "node_id": node_id,
    "node_type": node_type,
    "duration_ms": node_duration,
})

# On node failure (inside the inner except):
await ws_manager.send_event(execution_id, {
    "type": "node_failed",
    "node_id": node_id,
    "node_type": node_type,
    "error": str(e),
})

# At execution start (after setting status to "running"):
await ws_manager.send_event(execution_id, {
    "type": "execution_started",
})

# At execution completion:
await ws_manager.send_event(execution_id, {
    "type": "execution_completed",
    "execution_time_ms": total_time,
})

# At execution failure:
await ws_manager.send_event(execution_id, {
    "type": "execution_failed",
    "error": str(e),
})
```

---

## ISSUE 4 — `send_event` silently swallows exceptions and never cleans up dead connections

**File:** `backend/app/websocket/execution_ws.py`
**Lines:** 24–31

**Problem:**
```python
async def send_event(self, execution_id: str, event: dict):
    if execution_id in self.active_connections:
        message = json.dumps(event)
        for connection in self.active_connections[execution_id]:
            try:
                await connection.send_text(message)
            except Exception:
                pass   # dead connection stays in the list forever
```
When a send fails (client disconnected without a clean WebSocketDisconnect), the dead socket stays in `active_connections`. Every subsequent `send_event` retries sending to it, always fails, and always swallows the error. Over time this accumulates unbounded dead connections.

**Fix:** Collect dead connections during iteration and remove them after:
```python
async def send_event(self, execution_id: str, event: dict):
    if execution_id not in self.active_connections:
        return
    message = json.dumps(event)
    dead_connections = []
    for connection in self.active_connections[execution_id]:
        try:
            await connection.send_text(message)
        except Exception:
            dead_connections.append(connection)
    for conn in dead_connections:
        self.disconnect(conn, execution_id)
```

---

## ISSUE 5 — `disconnect` raises `ValueError` if the websocket is not in the list

**File:** `backend/app/websocket/execution_ws.py`
**Lines:** 18–22

**Problem:**
```python
def disconnect(self, websocket: WebSocket, execution_id: str):
    if execution_id in self.active_connections:
        self.active_connections[execution_id].remove(websocket)  # raises ValueError if not found
```
`list.remove(x)` raises `ValueError` if `x` is not in the list. This can happen if `disconnect` is called twice for the same websocket (e.g., once from the `except WebSocketDisconnect` block and once from `send_event` cleanup in Issue 4). The `ValueError` would propagate and crash the handler.

**Fix:** Guard the remove:
```python
def disconnect(self, websocket: WebSocket, execution_id: str):
    if execution_id in self.active_connections:
        try:
            self.active_connections[execution_id].remove(websocket)
        except ValueError:
            pass   # already removed
        if not self.active_connections[execution_id]:
            del self.active_connections[execution_id]
```

---

## ISSUE 6 — Receive loop ignores all client messages — no ping/pong heartbeat implemented

**File:** `backend/app/websocket/execution_ws.py`
**Lines:** 48–52

**Problem:**
```python
while True:
    data = await websocket.receive_text()
    # Client can send ping/pong or commands
```
The comment says "ping/pong or commands" but the received `data` is silently discarded. There is no heartbeat mechanism. If the client sends a `ping` message, there is no `pong` response. If the client sends a malformed message, there is no error feedback. The loop also has no timeout — a silent disconnect (without a clean close frame) will leave the connection open indefinitely until the TCP keepalive kills it.

**Fix:** Implement a basic message handler with ping/pong:
```python
try:
    while True:
        data = await websocket.receive_text()
        try:
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
        except (json.JSONDecodeError, TypeError):
            pass  # ignore malformed messages
except WebSocketDisconnect:
    manager.disconnect(websocket, execution_id)
```

---

## ISSUE 7 — `execution_websocket` does not handle unexpected exceptions — connection left dangling

**File:** `backend/app/websocket/execution_ws.py`
**Lines:** 47–54

**Problem:**
```python
await manager.connect(websocket, execution_id)
try:
    while True:
        data = await websocket.receive_text()
except WebSocketDisconnect:
    manager.disconnect(websocket, execution_id)
```
Only `WebSocketDisconnect` is caught. Any other exception (e.g., `RuntimeError` from Starlette, a bug in the message handler added by Issue 6, or an `asyncio.CancelledError` during shutdown) will:
1. Leave the websocket in `active_connections` forever (memory leak)
2. Potentially leave the WebSocket connection open without cleanup

**Fix:** Use a broader exception handler plus a `finally` block:
```python
await manager.connect(websocket, execution_id)
try:
    while True:
        data = await websocket.receive_text()
        # ... message handling ...
except WebSocketDisconnect:
    pass
except Exception:
    try:
        await websocket.close(code=1011, reason="Internal error")
    except Exception:
        pass
finally:
    manager.disconnect(websocket, execution_id)
```

---

## ISSUE 8 — `ConnectionManager` is a module-level singleton — incompatible with multi-worker deployments

**File:** `backend/app/websocket/execution_ws.py`
**Line:** 34

**Problem:**
```python
manager = ConnectionManager()   # in-memory, single-process
```
`active_connections` is an in-memory dict on a single Python process. In a deployment with multiple Uvicorn workers (or behind a load balancer), each worker has its own `ConnectionManager` instance. A client connecting to Worker A will never receive events broadcast from Worker B. The Celery worker (which runs in a completely separate process) also cannot call `manager.send_event()` at all.

**Fix (recommended):** Use a Redis pub/sub backend to broadcast events across workers:
```python
import aioredis

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
        self._pubsub = None

    async def init_pubsub(self):
        """Call during app lifespan startup."""
        from app.config import get_settings
        settings = get_settings()
        self._redis = aioredis.from_url(settings.REDIS_URL)
        self._pubsub = self._redis.pubsub()

    async def publish_event(self, execution_id: str, event: dict):
        """Publish an event to Redis so all workers receive it."""
        channel = f"execution:{execution_id}"
        await self._redis.publish(channel, json.dumps(event))

    async def subscribe(self, execution_id: str):
        """Subscribe to events for a specific execution."""
        channel = f"execution:{execution_id}"
        await self._pubsub.subscribe(channel)
```

Then update `main.py` lifespan to init pubsub on startup:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.websocket.execution_ws import manager
    await manager.init_pubsub()
    yield
```

> **Note:** This is a significant architectural change. As a minimum immediate fix, add a code comment documenting the single-process limitation and ensure the app is deployed with `--workers 1`.

---

## ISSUE 9 — `__init__.py` exports nothing — no public API for the websocket package

**File:** `backend/app/websocket/__init__.py`
**Line:** 1

**Problem:**
The file is empty. External code (`main.py`) must import directly from `app.websocket.execution_ws`, hardcoding the internal module structure. Adding a new WebSocket handler (e.g., for workspace events) would require updating every import site.

**Fix:** Export the public API:
```python
from app.websocket.execution_ws import manager, execution_websocket

__all__ = ["manager", "execution_websocket"]
```

---

## ISSUE 10 — `main.py`: WebSocket route is not behind CORS or origin checking

**File:** `backend/app/main.py`
**Lines:** 44–46

**Problem:**
```python
@app.websocket("/ws/executions/{execution_id}")
async def ws_execution(websocket: WebSocket, execution_id: str):
    await execution_websocket(websocket, execution_id)
```
FastAPI's `CORSMiddleware` (configured at lines 24–30) does **not** apply to WebSocket connections — it only handles HTTP preflight/OPTIONS requests. A malicious website can open a WebSocket to your server from any origin (Cross-Site WebSocket Hijacking / CSWSH).

**Fix:** Manually check the `Origin` header inside the WebSocket handler:
```python
async def execution_websocket(websocket: WebSocket, execution_id: str):
    # Check origin
    from app.config import get_settings
    settings = get_settings()
    origin = websocket.headers.get("origin", "")
    if origin and origin != settings.FRONTEND_URL:
        await websocket.close(code=4003, reason="Origin not allowed")
        return

    # ... rest of auth + connection logic ...
```

---

## Summary Table

| # | Severity | Category | One-Line Description |
|---|----------|----------|----------------------|
| 1 | **Critical** | Security | Auth is optional — unauthenticated access to execution streams |
| 2 | **High** | Security | No workspace authorization — any user can watch any execution |
| 3 | **Critical** | Functionality | `send_event` never called — WebSocket feature is non-functional |
| 4 | **High** | Resource Leak | Dead connections never removed from pool |
| 5 | **Medium** | Bug | `disconnect` raises `ValueError` on double-disconnect |
| 6 | **Medium** | Functionality | Client messages silently discarded, no heartbeat |
| 7 | **High** | Bug | Non-WebSocketDisconnect exceptions leave connections dangling |
| 8 | **High** | Architecture | In-memory manager incompatible with multi-worker deployment |
| 9 | **Low** | Style | Empty `__init__.py` — no public package API |
| 10 | **High** | Security | No WebSocket origin checking — CSWSH vulnerability |
