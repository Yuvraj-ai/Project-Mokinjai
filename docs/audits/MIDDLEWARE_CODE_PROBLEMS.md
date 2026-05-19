# Backend Middleware Code Problems And Fix Plan

Scope reviewed: `backend/app/middleware/__init__.py`, `backend/app/middleware/auth.py`, and `backend/app/middleware/rbac.py`.

This file is written as an implementation handoff for a CLI coding agent. Fix the middleware issues below, keep the changes scoped, and add focused tests for the behavior.

## Current Files

- `backend/app/middleware/auth.py`
- `backend/app/middleware/rbac.py`
- `backend/app/middleware/__init__.py`

## Problem 1: Missing Or Malformed Bearer Tokens Return The Wrong Status Code

Evidence:

- `backend/app/middleware/auth.py` defines `security = HTTPBearer()` with FastAPI's default `auto_error=True`.
- With that default, requests with no `Authorization` header or a malformed bearer header can fail inside `HTTPBearer` before `get_current_user()` runs.
- That commonly produces a `403 Not authenticated` response instead of the API's intended `401 Unauthorized` flow through `UnauthorizedException`.

Why this is a problem:

- Authentication failures should consistently return `401`.
- Clients often rely on `401` to trigger login/refresh behavior.
- The current behavior is inconsistent with the custom `UnauthorizedException` used later in `get_current_user()`.

Proper fix:

1. Change the bearer dependency to allow custom handling:

   ```python
   security = HTTPBearer(auto_error=False)
   ```

2. Update `get_current_user()` to accept optional credentials and explicitly reject missing credentials:

   ```python
   from typing import Annotated
   from fastapi import Depends
   from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

   security = HTTPBearer(auto_error=False)

   async def get_current_user(
       credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
       db: Annotated[AsyncSession, Depends(get_db)],
   ) -> User:
       if credentials is None:
           raise UnauthorizedException("Not authenticated")
       ...
   ```

3. Make sure all invalid token cases still raise `UnauthorizedException`.

4. Prefer adding a `WWW-Authenticate: Bearer` header to `UnauthorizedException` or to the raises in `get_current_user()` so clients know which auth scheme is required.

Suggested tests:

- Request a protected endpoint with no `Authorization` header and assert `401`.
- Request with `Authorization: Basic abc` or a malformed bearer value and assert `401`.
- Request with an invalid JWT and assert `401`.

## Problem 2: `UnauthorizedException` Does Not Include A Bearer Challenge Header

Evidence:

- `backend/app/utils/errors.py` defines `UnauthorizedException` with only `status_code` and `detail`.
- `backend/app/middleware/auth.py` uses this exception for all token failures.

Why this is a problem:

- HTTP auth clients expect `WWW-Authenticate: Bearer` on `401` responses from bearer-protected endpoints.
- Without the header, some clients and tooling cannot correctly detect the auth challenge.

Proper fix:

Option A, preferred if all `UnauthorizedException` usages are bearer auth failures:

```python
class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )
        self.headers = {"WWW-Authenticate": "Bearer"}
```

Option B, safer if some `UnauthorizedException` usages should not be bearer-specific:

```python
class UnauthorizedException(AppException):
    def __init__(
        self,
        detail: str = "Not authenticated",
        headers: dict[str, str] | None = None,
    ):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )
        self.headers = headers
```

Then raise bearer auth failures with:

```python
raise UnauthorizedException(
    "Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)
```

Suggested tests:

- For a protected endpoint without credentials, assert response header `www-authenticate` is `Bearer`.
- For an invalid token, assert the same header is present.

## Problem 3: Invalid Required Role Names Silently Allow Access

Evidence:

- `backend/app/middleware/rbac.py` maps unknown role names to level `0`:

  ```python
  min_level = ROLE_HIERARCHY.get(min_role, 0)
  user_level = ROLE_HIERARCHY.get(member.role, 0)
  ```

- If a route accidentally calls `Depends(require_workspace_role("edtor"))`, `min_level` becomes `0`.
- Any workspace member with a known role has a level greater than `0`, so the typo grants access to that route.

Why this is a problem:

- A typo in route configuration can silently downgrade authorization.
- This is a security-sensitive fail-open behavior.

Proper fix:

1. Validate `min_role` when the dependency is created and fail fast for invalid developer input:

   ```python
   def require_workspace_role(min_role: str = "viewer"):
       if min_role not in ROLE_HIERARCHY:
           raise ValueError(f"Unknown workspace role: {min_role}")

       async def dependency(...):
           ...

       return dependency
   ```

2. Validate the stored member role before comparing:

   ```python
   if member.role not in ROLE_HIERARCHY:
       raise ForbiddenException("Invalid workspace role")
   ```

3. Consider moving roles to a shared enum or `Literal["owner", "admin", "editor", "viewer"]` so route code and schemas cannot drift.

Suggested tests:

- Calling `require_workspace_role("bad-role")` should raise `ValueError`.
- A member row with an unknown role should not be authorized.
- Normal hierarchy checks should still pass: owner >= admin >= editor >= viewer.

## Problem 4: RBAC Dependency Is Too Implicit About Where `workspace_id` Comes From

Evidence:

- `require_workspace_role()` declares an inner dependency parameter named `workspace_id: str`.
- FastAPI resolves this by matching a path/query parameter with the same name.
- Current routers include `workspace_id` in their route prefix, so existing usage works.
- If a future route uses this dependency without a path parameter named exactly `workspace_id`, FastAPI may treat `workspace_id` as a required query parameter instead.

Why this is a problem:

- A future endpoint can accidentally authorize against a user-supplied query parameter instead of a path-scoped workspace.
- The dependency's security boundary is hidden in a parameter-name convention.

Proper fix:

Use `Request.path_params` so RBAC only trusts the route path context:

```python
from fastapi import Depends, Request

def require_workspace_role(min_role: str = "viewer"):
    if min_role not in ROLE_HIERARCHY:
        raise ValueError(f"Unknown workspace role: {min_role}")

    async def dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> WorkspaceMember:
        workspace_id = request.path_params.get("workspace_id")
        if not workspace_id:
            raise RuntimeError("require_workspace_role requires a {workspace_id} path parameter")
        ...

    return dependency
```

Alternative acceptable fix:

- Keep `workspace_id: str`, but annotate it with `Path(...)` and document that this dependency may only be used on routes with `{workspace_id}` in the path.
- The `Request.path_params` approach is harder to misuse.

Suggested tests:

- A route with `/workspaces/{workspace_id}` should authorize normally.
- A route using `require_workspace_role()` without `{workspace_id}` should fail loudly during test execution instead of accepting `?workspace_id=...`.

## Problem 5: Token Failure Details Leak Too Much Internal State

Evidence:

- `get_current_user()` raises `UnauthorizedException("User not found")` when a token is validly signed but points to a deleted or nonexistent user.

Why this is a problem:

- Auth failures should usually be indistinguishable to clients.
- Returning `"User not found"` exposes account state and creates a different response for deleted-user tokens versus other invalid tokens.

Proper fix:

- Replace `"User not found"` with a generic auth failure message, such as `"Invalid or expired token"`.
- Keep any detailed reason in server logs if needed.

Suggested tests:

- A token whose `sub` does not match a user should return `401` with a generic detail.

## Problem 6: Middleware Has Minor Type And Cleanup Issues

Evidence:

- `backend/app/middleware/auth.py` imports `Request` but never uses it.
- `app.utils.security.decode_token()` is annotated as returning `dict`, but it returns `None` on decode failure. `get_current_user()` correctly checks for `None`, but the typing is inaccurate.
- `backend/app/middleware/__init__.py` is empty, which is valid, but it does not provide a stable export surface for the middleware dependencies.

Why this is a problem:

- Unused imports and inaccurate annotations make static analysis noisier.
- Incorrect return typing can hide real `None` handling issues from type checkers.
- Empty `__init__.py` is not a runtime bug, but exporting common dependencies can make imports cleaner if the project wants that pattern.

Proper fix:

1. Remove the unused `Request` import from `auth.py` unless Problem 4 is fixed using `Request` in `rbac.py`.
2. Update `decode_token()` in `backend/app/utils/security.py` to return `dict | None`.
3. Optionally add explicit exports in `backend/app/middleware/__init__.py`:

   ```python
   from app.middleware.auth import get_current_user
   from app.middleware.rbac import require_workspace_role

   __all__ = ["get_current_user", "require_workspace_role"]
   ```

Suggested tests/checks:

- Run `python -m py_compile backend/app/middleware/auth.py backend/app/middleware/rbac.py backend/app/middleware/__init__.py`.
- If a linter/type checker exists later, it should not flag the stale import or `decode_token()` return type.

## Recommended Implementation Order

1. Update auth credential handling in `auth.py` to use `HTTPBearer(auto_error=False)`.
2. Add bearer challenge headers for `401` responses.
3. Harden `require_workspace_role()` against invalid `min_role` and invalid stored roles.
4. Make RBAC read `workspace_id` from path params or explicitly require a path parameter.
5. Normalize token failure messages.
6. Clean up imports/types and add optional middleware exports.
7. Add focused middleware tests.

## Verification Commands

Run these after implementing fixes:

```bash
python -m py_compile backend/app/middleware/auth.py backend/app/middleware/rbac.py backend/app/middleware/__init__.py
pytest backend/tests -q
```

If the full backend currently has unrelated syntax errors, keep middleware tests isolated until those unrelated files are repaired.

## Notes For The CLI Agent

- Do not change unrelated routers or models unless a test requires a tiny fixture-only adjustment.
- Preserve the existing role order: `owner > admin > editor > viewer`.
- Keep response status behavior stable except where this report explicitly calls for `401` instead of `403` on authentication failures.
- Add tests that fail before the middleware fixes and pass after them.
