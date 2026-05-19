# Backend Utils Code Problems And Fix Plan

Scope reviewed: `backend/app/utils`.

This file is written as an implementation handoff for a CLI coding agent. Fix the problems in priority order, keep changes scoped, and add tests for security and failure behavior.

## Current Files

- `backend/app/utils/__init__.py`
- `backend/app/utils/errors.py`
- `backend/app/utils/mongo.py`
- `backend/app/utils/security.py`

## Problem 1: `UnauthorizedException` Does Not Send A Bearer Challenge Header

Evidence:

- `backend/app/utils/errors.py` defines `UnauthorizedException` with only `status_code` and `detail`.
- `backend/app/middleware/auth.py` and `backend/app/routers/auth.py` use `UnauthorizedException` for bearer-token failures.

Why this is a problem:

- HTTP bearer auth failures should return `WWW-Authenticate: Bearer` with `401`.
- Clients often rely on that header to identify auth failures and trigger login/refresh behavior.

Proper fix:

Option A, preferred if all `UnauthorizedException` use is bearer-auth related:

```python
class AppException(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )
```

Option B, if some `401` responses should not be bearer-specific:

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
            headers=headers,
        )
```

Then pass `headers={"WWW-Authenticate": "Bearer"}` at auth failure call sites.

Suggested tests:

- Protected endpoint without credentials returns `401` and `WWW-Authenticate: Bearer`.
- Invalid access token returns `401` and the same header.

## Problem 2: `AppException` Cannot Pass Headers

Evidence:

- `AppException.__init__()` accepts only `status_code` and `detail`.
- FastAPI's `HTTPException` supports `headers`, but the project wrapper drops that ability.

Why this is a problem:

- Auth challenge headers cannot be added cleanly.
- Future errors such as rate-limit responses cannot set headers like `Retry-After`.

Proper fix:

Update `AppException` to accept and forward headers:

```python
class AppException(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
```

Suggested tests:

- Construct `AppException(..., headers={"X-Test": "1"})` and assert `exc.headers == {"X-Test": "1"}`.

## Problem 3: `decode_token()` Return Type Is Wrong

Evidence:

- `backend/app/utils/security.py` declares `def decode_token(token: str) -> dict:`.
- It returns `None` on `JWTError`.
- Callers already check `payload is None`.

Why this is a problem:

- Type checkers and IDEs are told `None` cannot happen.
- Future callers may skip `None` handling and crash.

Proper fix:

```python
from typing import Any

def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None
```

Suggested tests:

- Invalid token returns `None`.
- Valid access token returns a dict payload.

## Problem 4: Password Verification Can Raise And Produce A 500

Evidence:

- `verify_password()` directly calls `bcrypt.checkpw(...)`.
- If `hashed_password` is malformed or uses an unsupported format, `bcrypt.checkpw()` can raise `ValueError`.
- `auth.login()` does not catch this exception.

Why this is a problem:

- A corrupted password hash can turn a login attempt into a server error.
- Auth failures should fail closed with `False`, not leak implementation errors.

Proper fix:

```python
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False
```

Suggested tests:

- `verify_password("secret", "not-a-bcrypt-hash")` returns `False`.
- Login with a malformed stored hash returns `401`, not `500`.

## Problem 5: Direct `bcrypt` Usage Needs Password Length Handling

Evidence:

- `hash_password()` passes the full UTF-8 password into bcrypt.
- Bcrypt only uses the first 72 bytes of the password.
- The schema currently accepts arbitrary password length.

Why this is a problem:

- Two passwords that match for the first 72 bytes can verify as the same password.
- Users may believe long passwords are fully used when bcrypt truncates them.

Proper fix:

Minimum:

- Add request schema validation to cap password length at 72 bytes or 72 ASCII characters.
- Reject passwords whose UTF-8 encoding exceeds 72 bytes.

Better:

- Pre-hash passwords with SHA-256 before bcrypt, or use a password hashing library pattern that handles long passwords intentionally.
- If using passlib, switch to `CryptContext` and configure the policy explicitly.

Example direct-bcrypt guard:

```python
MAX_BCRYPT_PASSWORD_BYTES = 72

def _password_bytes(password: str) -> bytes:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError("Password exceeds bcrypt's 72-byte limit")
    return password_bytes
```

Suggested tests:

- Password over 72 UTF-8 bytes is rejected consistently at registration.
- Hash/verify works for a valid password.

## Problem 6: Security Utilities Use Import-Time Settings Snapshot

Evidence:

- `security.py` sets `settings = get_settings()` at import time.
- `mongo.py` also sets `settings = get_settings()` at import time.
- Tests or runtime configuration changes after import will not be reflected.

Why this is a problem:

- Tests that override settings can accidentally keep using old JWT secrets or Mongo URLs.
- Long-lived processes cannot pick up configuration overrides without restart.

Proper fix:

For security utilities, fetch settings inside functions or inject settings in tests:

```python
def create_access_token(data: dict[str, Any]) -> str:
    settings = get_settings()
    ...
```

For Mongo utilities, fetch settings when creating the client:

```python
def get_client(cls) -> AsyncIOMotorClient:
    settings = get_settings()
    ...
```

Suggested tests:

- Override `get_settings.cache_clear()` and environment variables in a test, then assert token creation uses the new secret.

## Problem 7: JWT Tokens Have No `iat`, `jti`, Issuer, Audience, Or Revocation Hook

Evidence:

- `create_access_token()` and `create_refresh_token()` include only caller-provided data plus `exp` and `type`.
- Refresh tokens are accepted until expiration if the signature is valid.
- There is no token ID or revocation check.

Why this is a problem:

- Stolen refresh tokens remain reusable until expiry.
- Tokens cannot be individually revoked.
- If this API later has multiple clients/services, issuer and audience checks will matter.

Proper fix:

Minimum:

```python
import uuid

now = datetime.now(timezone.utc)
to_encode.update({
    "iat": now,
    "exp": expire,
    "jti": str(uuid.uuid4()),
    "type": "access",
})
```

Better:

- Add configured `JWT_ISSUER` and `JWT_AUDIENCE`.
- Include `iss` and `aud` in token creation.
- Validate `issuer=` and `audience=` in `jwt.decode()`.
- Store refresh token `jti` hashes server-side and rotate refresh tokens on use.

Suggested tests:

- Created tokens include `iat`, `exp`, `jti`, and `type`.
- Refresh token reuse fails after rotation once token storage is implemented.

## Problem 8: JWT Decode Does Not Validate Token Type

Evidence:

- `decode_token()` only verifies signature/expiration.
- Token type validation is repeated in callers such as `get_current_user()` and `refresh_token()`.
- `execution_websocket()` decodes a token but does not check `payload["type"] == "access"`.

Why this is a problem:

- Callers can forget to check token type.
- A refresh token can be accepted by a caller that only calls `decode_token()`.

Proper fix:

Add a helper that validates type:

```python
def decode_token(token: str) -> dict[str, Any] | None:
    ...

def decode_token_of_type(token: str, expected_type: str) -> dict[str, Any] | None:
    payload = decode_token(token)
    if payload is None or payload.get("type") != expected_type:
        return None
    return payload
```

Then use:

- `decode_token_of_type(token, "access")` for auth middleware and WebSockets.
- `decode_token_of_type(token, "refresh")` for refresh route.

Suggested tests:

- Refresh token is rejected by access-token helper.
- Access token is rejected by refresh-token helper.
- WebSocket auth rejects refresh tokens.

## Problem 9: Mongo Client Has No Close Hook Or Lifespan Integration

Evidence:

- `MongoManager` stores a process-global `AsyncIOMotorClient`.
- There is no `close()` method.
- `main.py` lifespan does not close the Mongo client on shutdown.

Why this is a problem:

- Test suites can leak sockets across tests.
- App shutdown does not close Mongo connections cleanly.
- Reconfiguration is hard once a client has been created.

Proper fix:

Add close/reset methods:

```python
class MongoManager:
    client: AsyncIOMotorClient | None = None

    @classmethod
    def close(cls) -> None:
        if cls.client is not None:
            cls.client.close()
            cls.client = None
```

Then call it in FastAPI lifespan shutdown:

```python
from app.utils.mongo import MongoManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    MongoManager.close()
```

Suggested tests:

- Create client, call `MongoManager.close()`, assert `MongoManager.client is None`.

## Problem 10: Mongo Client Has No Timeout Or Connectivity Check

Evidence:

- `MongoManager.get_client()` creates `AsyncIOMotorClient(url)` with default timeouts.
- `get_mongo_db()` returns a database handle without checking connectivity.

Why this is a problem:

- A bad Mongo URL may fail later inside blob operations with slow timeouts.
- Startup can appear healthy even though required blob storage is unreachable.

Proper fix:

Configure a reasonable timeout:

```python
cls.client = AsyncIOMotorClient(
    url,
    serverSelectionTimeoutMS=5000,
)
```

Add a health helper:

```python
@classmethod
async def ping(cls) -> None:
    await cls.get_client().admin.command("ping")
```

Then optionally call it during app startup if Mongo is required.

Suggested tests:

- `get_client()` passes configured timeout options.
- Health endpoint or startup check reports Mongo failures intentionally if blob storage is required.

## Problem 11: Mongo Configuration Fallback Can Hide Misconfiguration

Evidence:

- `mongo.py` uses `settings.MONGO_URL if settings.MONGO_URL else "mongodb://localhost:27017"`.
- `config.py` currently provides a non-empty default Atlas-style URL with a placeholder password.

Why this is a problem:

- Local development may unexpectedly try to connect to a placeholder Atlas URL instead of localhost.
- Production with an empty `MONGO_URL` would silently use localhost, which is unsafe and confusing.

Proper fix:

- Move fallback behavior into configuration, not utility code.
- Validate that placeholder values are not used outside local development.
- Prefer explicit defaults:

```python
MONGO_URL: str = "mongodb://localhost:27017"
```

or require it:

```python
MONGO_URL: str
```

Then simplify `mongo.py`:

```python
url = get_settings().MONGO_URL
cls.client = AsyncIOMotorClient(url, serverSelectionTimeoutMS=5000)
```

Suggested tests:

- Missing/placeholder Mongo URL fails fast in production settings.
- Local settings use a local Mongo URL intentionally.

## Problem 12: Mongo Type Annotation Is Inaccurate

Evidence:

- `MongoManager.client: AsyncIOMotorClient = None` assigns `None` to a non-optional type.
- `get_db()` has no return type.
- `get_mongo_db()` is async but only returns a database handle without awaiting anything.

Why this is a problem:

- Type checking is noisy or misleading.
- The async wrapper suggests I/O happens when it does not.

Proper fix:

```python
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

class MongoManager:
    client: AsyncIOMotorClient | None = None

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        ...

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        return cls.get_client()[get_settings().MONGO_DB_NAME]

def get_mongo_db() -> AsyncIOMotorDatabase:
    return MongoManager.get_db()
```

If keeping `get_mongo_db()` async for API consistency, document why.

Suggested tests/checks:

- Static type checking should not complain about assigning `None`.
- Blob service call sites should be updated if `get_mongo_db()` becomes sync.

## Problem 13: Utility Package Has No Stable Export Surface

Evidence:

- `backend/app/utils/__init__.py` is empty.
- Callers import from individual utility modules directly.

Why this is a problem:

- This is not a runtime bug.
- It can make utility discovery harder for future agents.

Proper fix:

Either leave it empty and keep direct module imports as the convention, or add explicit exports:

```python
from app.utils.errors import (
    AppException,
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

__all__ = [...]
```

Suggested checks:

- Importing `app.utils` should not create circular imports or initialize external connections.

## Recommended Implementation Order

1. Update `AppException` to support headers.
2. Add bearer `WWW-Authenticate` headers to `UnauthorizedException` or auth call sites.
3. Fix `decode_token()` typing and add typed token helper functions.
4. Harden password hashing/verification around malformed hashes and bcrypt length limits.
5. Add JWT `iat`/`jti` and plan refresh-token revocation.
6. Remove import-time settings snapshots from utility modules.
7. Add Mongo timeout, close/reset hook, and accurate typing.
8. Make Mongo configuration explicit and fail fast on placeholder production values.
9. Optionally add `utils.__init__` exports.
10. Add focused tests.

## Verification Commands

Run these after implementing fixes:

```bash
python -m py_compile backend/app/utils/*.py
python - <<'PY'
from app.utils.errors import UnauthorizedException
from app.utils.security import create_access_token, decode_token, verify_password
from app.utils.mongo import MongoManager
print("utils imports ok")
PY
pytest backend/tests -q
```

If running from inside `backend`, use:

```bash
cd backend
python - <<'PY'
from app.utils.errors import UnauthorizedException
from app.utils.security import create_access_token, decode_token, verify_password
from app.utils.mongo import MongoManager
print("utils imports ok")
PY
pytest tests -q
```

## Notes For The CLI Agent

- Do not edit unrelated frontend files.
- Preserve existing user-owned uncommitted changes, especially the untracked `backend/app/utils/mongo.py`, unless the utility fix must build on them.
- Keep utility changes aligned with middleware, routers, WebSocket auth, `BlobService`, and app lifespan.
- Mock MongoDB in utility tests; do not require a live Atlas/local Mongo instance for unit tests.
- Security fixes should fail closed: malformed tokens, malformed hashes, and missing config should not become `500` responses or silent success.
