# God Mode Plan: Backend Stabilization Sprint

## Sprint Context
**Objective:** Resolve all critical syntax errors, logic bugs, security vulnerabilities, and infrastructure gaps identified in the backend audit reports.
**Current State:** App fails to start due to syntax corruption; hybrid DB integration is inconsistent.
**Target State:** Stable, production-ready backend with 100% functional execution engine and secure auth.

---

## Work Units (4 Parallel Tracks)

### Track 1: Survival & Infrastructure (Critical)
*   **T1.1: Syntax Repair**
    *   **Agent:** builder-1
    *   **Files:** `backend/app/routers/executions.py`, `backend/app/routers/workflows.py`, `backend/app/schemas/execution.py`
    *   **Task:** Remove garbled duplicate code and add missing `Decimal` import.
*   **T1.2: Config & Lifecycle**
    *   **Agent:** builder-1
    *   **Files:** `backend/app/config.py`, `backend/app/main.py`, `backend/app/database.py`
    *   **Task:** Fix insecure defaults, implement lifespan cleanup, and prevent import-time resource capture.
*   **T1.3: SQLite & Migrations**
    *   **Agent:** builder-1
    *   **Files:** `backend/app/database.py`, `backend/alembic/env.py`
    *   **Task:** Enable SQLite foreign keys and fix sync URL conversion helper.

### Track 2: Data Integrity & Hybrid DB (High)
*   **T2.1: Router-Blob Synchronization**
    *   **Agent:** builder-2
    *   **Files:** `backend/app/routers/workflows.py`, `backend/app/routers/executions.py`, `backend/app/services/blob_service.py`
    *   **Task:** Harmonize routers with `BlobService` (Mongo Atlas), handle orphaned blobs, and fix `get_blob` ID validation.
*   **T2.2: Model & Schema Hardening**
    *   **Agent:** builder-2
    *   **Files:** `backend/app/models/*.py`, `backend/app/schemas/*.py`
    *   **Task:** Fix `WorkflowVersion` uniqueness, standardize timezones (aware), and add `Literal` constraints for roles/statuses.
*   **T2.3: Mutation Tracking**
    *   **Agent:** builder-2
    *   **Files:** `backend/app/models/*.py`
    *   **Task:** Use `MutableDict.as_mutable` for JSON columns to ensure in-place updates are persisted.

### Track 3: Execution Engine & Modules (High)
*   **T3.1: Executor Robustness**
    *   **Agent:** builder-3
    *   **Files:** `backend/app/engine/executor.py`, `backend/app/engine/context.py`
    *   **Task:** Fix `start_time` placement, `'context' in locals()` fragility, and terminal node output logic.
*   **T3.2: Graph Validation**
    *   **Agent:** builder-3
    *   **Files:** `backend/app/engine/dag_builder.py`
    *   **Task:** Implement iterative (non-recursive) cycle detection and deduplicate edges in `_build`.
*   **T3.3: Module Resilience**
    *   **Agent:** builder-3
    *   **Files:** `backend/app/engine/modules/*.py`
    *   **Task:** Add `raise_for_status` to HTTP module, fix Gemini usage metadata handling, and use cached LLM clients.

### Track 4: Auth, RBAC & Communication (Medium)
*   **T4.1: Security Middleware**
    *   **Agent:** builder-1 (post-Track 1)
    *   **Files:** `backend/app/middleware/*.py`, `backend/app/utils/errors.py`
    *   **Task:** Align 401/403 status codes, add bearer challenge headers, and harden `require_workspace_role` against typos.
*   **T4.2: Workers & WebSockets**
    *   **Agent:** builder-1
    *   **Files:** `backend/app/workers/*.py`, `backend/app/websocket/*.py`
    *   **Task:** Fix Celery autodiscovery/retries and WebSocket broadcast/cleanup logic (Redis pub/sub placeholder).

---

## Dependency Graph

`T1.1` (Syntax) ──► `T1.2` (Config) ──► `T2.1` (Hybrid DB)
                                 ├──► `T3.1` (Executor)
`T1.3` (SQLite) ──► `T2.2` (Models)
`T2.1` ──► `T4.1` (Auth/RBAC)
`T3.1` ──► `T4.2` (Workers/WS)

---

## Risk Assessment
*   **Merge Conflict Risk:** Medium. Many changes touch the same router and engine files. **Track 1 must be completed first** to provide a stable base.
*   **Data Loss:** Resetting Alembic migrations is necessary for SQLite transition. Local Postgres data will be lost.
*   **LLM API Breaking Changes:** Gemini usage metadata handling needs careful alignment with latest SDK.

---

## Verification Strategy
[ ] `python -m py_compile` passes for all backend files.
[ ] `pytest` (mocked) passes for all routers.
[ ] SQLite database maintains referential integrity (foreign keys).
[ ] MongoDB Atlas stores flow definitions and traces correctly.
[ ] WebSocket receives `execution_started` and `execution_completed` events.
[ ] 401 Unauthorized returned for missing/invalid tokens with challenge header.
