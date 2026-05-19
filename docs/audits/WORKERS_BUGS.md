# Workers Bug Report — `backend/app/workers/`

> **Purpose:** Read by a CLI agent. Fix each issue in order. Do NOT skip any issue.
> Scope covers `celery_app.py`, `execution_worker.py`, and `__init__.py`.

---

## ISSUE 1 — `execution_worker.py`: `max_retries=3` declared but `self.retry()` is never called — retries never trigger

**File:** `backend/app/workers/execution_worker.py`
**Lines:** 7–15

**Problem:**
```python
@celery_app.task(name="run_workflow", bind=True, max_retries=3)
def run_workflow_task(self, execution_id: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_execute(execution_id))
    finally:
        loop.close()
```
The task is configured with `max_retries=3` and `bind=True` (giving access to `self`), but no `except` block ever calls `self.retry(exc=e)`. When `_execute` raises, the exception propagates directly out of the task, Celery marks it as `FAILURE`, and no retry is attempted. The `max_retries=3` configuration has zero effect.

**Fix:**
```python
@celery_app.task(name="run_workflow", bind=True, max_retries=3, default_retry_delay=10)
def run_workflow_task(self, execution_id: str):
    """Celery task to execute a workflow asynchronously."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_execute(execution_id))
    except Exception as exc:
        try:
            loop.close()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        if not loop.is_closed():
            loop.close()
```

---

## ISSUE 2 — `execution_worker.py`: `asyncio.set_event_loop(loop)` pollutes the thread's global loop state

**File:** `backend/app/workers/execution_worker.py`
**Lines:** 10–11

**Problem:**
```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
```
`asyncio.set_event_loop(loop)` sets the loop as the **thread-global** default event loop. In Celery's prefork worker pool, each worker process handles tasks sequentially, so this is not an immediate race condition. However:
1. If using the `threads` or `gevent` pool, multiple tasks could clobber each other's loop.
2. After `loop.close()` in `finally`, the thread's global loop is now a closed loop — any subsequent code that calls `asyncio.get_event_loop()` on that thread gets a closed loop and crashes.

**Fix:** Don't set the global loop. Use `loop.run_until_complete()` directly (it doesn't require the loop to be the global default):
```python
@celery_app.task(name="run_workflow", bind=True, max_retries=3, default_retry_delay=10)
def run_workflow_task(self, execution_id: str):
    """Celery task to execute a workflow asynchronously."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_execute(execution_id))
    except Exception as exc:
        raise self.retry(exc=exc)
    finally:
        loop.close()
```

---

## ISSUE 3 — `execution_worker.py`: DB session is not committed/rolled back on unhandled async exceptions

**File:** `backend/app/workers/execution_worker.py`
**Lines:** 18–21

**Problem:**
```python
async def _execute(execution_id: str):
    async with async_session() as db:
        executor = WorkflowExecutor(db)
        await executor.execute(execution_id)
```
The `async with async_session() as db` context manager closes the session on exit, but does NOT automatically commit or rollback. If `executor.execute()` raises an exception *after* making partial changes (e.g., setting `execution.status = "running"` and committing, then failing later with an error that the executor's own `except` block fails to handle), the session exits without a final commit. This can leave the execution record stuck in `"running"` status permanently.

**Fix:** Add explicit error handling with a rollback and a safety-net status update:
```python
async def _execute(execution_id: str):
    async with async_session() as db:
        try:
            executor = WorkflowExecutor(db)
            await executor.execute(execution_id)
        except Exception:
            await db.rollback()
            # Safety net: mark execution as failed if it's still "running"
            from sqlalchemy import select, update
            from app.models.execution import Execution
            from datetime import datetime, timezone
            await db.execute(
                update(Execution)
                .where(Execution.id == execution_id, Execution.status == "running")
                .values(
                    status="failed",
                    error_message="Worker crashed during execution",
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            raise
```

---

## ISSUE 4 — `execution_worker.py`: Retrying a failed execution re-runs from scratch without resetting state

**File:** `backend/app/workers/execution_worker.py`
**Lines:** 7–21

**Problem:**
When Issue 1 is fixed and retries are enabled, `self.retry(exc=exc)` will re-invoke `run_workflow_task` with the same `execution_id`. But the `Execution` record in the DB may already be in `status="failed"` (set by the executor's `except` block), with partial `output_data`, `mongo_trace_id`, etc. The executor's `execute()` method at line 41 sets `status="running"` again, but the old trace data in MongoDB is not cleaned up, and `started_at` is overwritten — losing the original start time.

Not all failures are retryable either. An `InvalidId` from bad blob IDs or a `BadRequestException` from cycle detection should NOT be retried.

**Fix:** Reset execution state before retry, and only retry on transient errors:
```python
TRANSIENT_ERRORS = (ConnectionError, TimeoutError, OSError)

@celery_app.task(name="run_workflow", bind=True, max_retries=3, default_retry_delay=10)
def run_workflow_task(self, execution_id: str):
    """Celery task to execute a workflow asynchronously."""
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_execute(execution_id))
    except TRANSIENT_ERRORS as exc:
        raise self.retry(exc=exc)
    except Exception:
        pass  # non-retryable — executor already marked it as failed in the DB
    finally:
        loop.close()
```

---

## ISSUE 5 — `celery_app.py`: Module-level `get_settings()` — Celery worker crashes if `.env` is missing

**File:** `backend/app/workers/celery_app.py`
**Lines:** 1–10

**Problem:**
```python
from app.config import get_settings

settings = get_settings()        # called at import time

celery_app = Celery(
    "agent_builder",
    broker=settings.REDIS_URL,   # baked in at import
    backend=settings.REDIS_URL,
)
```
`get_settings()` is called at module-level import time. If `.env` is not present or `REDIS_URL` is unset, this raises immediately and prevents the Celery worker from even starting — with a confusing Pydantic validation error rather than a clear "missing REDIS_URL" message. The `REDIS_URL` is also baked in at import time, so it cannot be overridden by test fixtures or environment changes after import.

**Fix:** Use lazy configuration:
```python
from celery import Celery

celery_app = Celery("agent_builder")

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


def configure_celery():
    """Call this during worker startup to bind broker/backend from settings."""
    from app.config import get_settings
    settings = get_settings()
    celery_app.conf.update(
        broker_url=settings.REDIS_URL,
        result_backend=settings.REDIS_URL,
    )


# Auto-configure when loaded as a Celery worker
configure_celery()
```

---

## ISSUE 6 — `celery_app.py`: No task autodiscovery configured — tasks must be explicitly imported

**File:** `backend/app/workers/celery_app.py`

**Problem:**
The Celery app has no `autodiscover_tasks()` call and no `include` config. Tasks are only registered because `execution_worker.py` is explicitly imported at the call site (line 56 of `routers/executions.py`: `from app.workers.execution_worker import run_workflow_task`). If the Celery worker process is started with `celery -A app.workers.celery_app worker`, it has no knowledge of `execution_worker.py` and will reject incoming tasks with `Received unregistered task`.

**Fix:** Add autodiscovery:
```python
celery_app.autodiscover_tasks(["app.workers"])
```
Or explicitly include:
```python
celery_app.conf.update(
    include=["app.workers.execution_worker"],
    # ... rest of config
)
```

---

## ISSUE 7 — `celery_app.py`: No dead-letter queue or error callback — failed tasks are silently lost

**File:** `backend/app/workers/celery_app.py`

**Problem:**
There is no `task_reject_on_worker_lost`, no dead-letter queue configuration, and no `on_failure` callback. If a worker is killed mid-task (OOM kill, deployment restart), the task vanishes. With `task_acks_late=True` (line 19), Celery will re-deliver the message if the worker dies before acking — but if the worker acks and then crashes (which is the default with `acks_late` + `reject_on_worker_lost=False`), the task is lost.

**Fix:** Add worker-lost rejection and a failure handler:
```python
celery_app.conf.update(
    # ... existing config ...
    task_reject_on_worker_lost=True,   # re-queue if worker is killed
    task_time_limit=600,               # hard kill after 10 minutes
    task_soft_time_limit=540,          # raise SoftTimeLimitExceeded at 9 min
)
```
And add an `on_failure` callback to the task:
```python
@celery_app.task(name="run_workflow", bind=True, max_retries=3, default_retry_delay=10)
def run_workflow_task(self, execution_id: str):
    # ... existing code ...

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Update execution status when all retries are exhausted."""
        execution_id = args[0] if args else kwargs.get("execution_id")
        if execution_id:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_mark_failed(execution_id, str(exc)))
            finally:
                loop.close()
```

---

## ISSUE 8 — `celery_app.py`: No task time limit — a stuck LLM call can block the worker forever

**File:** `backend/app/workers/celery_app.py`

**Problem:**
There is no `task_time_limit` or `task_soft_time_limit` configured. If a workflow contains an `AgentModule` that calls an LLM API and the API hangs indefinitely (no timeout on the HTTP client side), the Celery worker thread is blocked forever. With `worker_prefetch_multiplier=1`, this means the entire worker process is stuck on one task.

**Fix:** (Covered in Issue 7) Add time limits:
```python
celery_app.conf.update(
    task_time_limit=600,         # hard kill after 10 minutes
    task_soft_time_limit=540,    # raise SoftTimeLimitExceeded at 9 minutes
)
```

---

## ISSUE 9 — `execution_worker.py`: No logging — failures are completely invisible

**File:** `backend/app/workers/execution_worker.py`
**Lines:** 7–21

**Problem:**
The entire worker module has no logging. When an execution fails, the exception is silently swallowed (after Issue 1 is fixed with retries) or at best appears in Celery's generic task error output. There is no structured logging of which `execution_id` started, succeeded, failed, or was retried. Debugging production failures requires guessing.

**Fix:** Add structured logging:
```python
import asyncio
import logging
from app.workers.celery_app import celery_app
from app.database import async_session
from app.engine.executor import WorkflowExecutor

logger = logging.getLogger(__name__)


@celery_app.task(name="run_workflow", bind=True, max_retries=3, default_retry_delay=10)
def run_workflow_task(self, execution_id: str):
    """Celery task to execute a workflow asynchronously."""
    logger.info("Starting workflow execution", extra={"execution_id": execution_id, "attempt": self.request.retries + 1})
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_execute(execution_id))
        logger.info("Workflow execution completed", extra={"execution_id": execution_id})
    except Exception as exc:
        logger.error("Workflow execution failed", extra={"execution_id": execution_id, "error": str(exc)}, exc_info=True)
        raise self.retry(exc=exc)
    finally:
        loop.close()
```

---

## ISSUE 10 — `execution_worker.py`: Caller passes `execution.id` (UUID string) but task serializer is JSON — type safety risk

**File:** `backend/app/routers/executions.py` line 57, `backend/app/workers/execution_worker.py` line 8

**Problem:**
```python
# In routers/executions.py:
run_workflow_task.delay(execution.id)

# In execution_worker.py:
def run_workflow_task(self, execution_id: str):
```
`execution.id` is a UUID string generated by `str(uuid.uuid4())`. The Celery task serializer is `json`, which serializes this correctly as a string. However, there is no validation on the receiving end that `execution_id` is a valid UUID. If the task is invoked manually (via Celery CLI, Flower, or another producer) with a non-UUID value, the executor will run a SQL query with a garbage ID and get `None` back, raising a generic `ValueError("Execution ... not found")` with no indication that the input was malformed.

**Fix:** Validate the input at the task boundary:
```python
import uuid as uuid_mod

@celery_app.task(name="run_workflow", bind=True, max_retries=3, default_retry_delay=10)
def run_workflow_task(self, execution_id: str):
    """Celery task to execute a workflow asynchronously."""
    try:
        uuid_mod.UUID(execution_id)
    except (ValueError, AttributeError):
        logger.error("Invalid execution_id received", extra={"execution_id": execution_id})
        return  # don't retry — input is permanently invalid

    # ... rest of task ...
```

---

## Summary Table

| # | File | Severity | Category | One-Line Description |
|---|------|----------|----------|----------------------|
| 1 | execution_worker.py | **Critical** | Bug | `max_retries=3` has no effect — `self.retry()` never called |
| 2 | execution_worker.py | Medium | Bug | `set_event_loop` pollutes thread state, leaves closed loop behind |
| 3 | execution_worker.py | High | Data Integrity | No rollback/safety-net — executions can get stuck in "running" |
| 4 | execution_worker.py | High | Logic | Retries re-run from scratch without resetting state or filtering non-retryable errors |
| 5 | celery_app.py | Medium | Startup | Module-level `get_settings()` crashes if `.env` missing |
| 6 | celery_app.py | **Critical** | Configuration | No task autodiscovery — standalone worker rejects all tasks |
| 7 | celery_app.py | High | Reliability | No dead-letter queue or `reject_on_worker_lost` — tasks lost on crash |
| 8 | celery_app.py | High | Reliability | No task time limit — stuck LLM calls block worker forever |
| 9 | execution_worker.py | Medium | Observability | Zero logging — failures completely invisible |
| 10 | execution_worker.py | Low | Validation | No UUID validation on `execution_id` input |
