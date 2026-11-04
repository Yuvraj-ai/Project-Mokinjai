"""Public API-key authentication (plan Task 3).

The /v1 credential is a bearer `mk_` key resolved from `api_keys`. It is
deliberately separate from the human-session dependency: a session token
must never open /v1 and a key must never open /api, in both directions.
"""

import uuid
from datetime import datetime, timezone

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import logger
from app.models.api_key import ApiKey
from app.services.api_keys import hash_secret

_LAST_USED_THROTTLE_S = 60


class PublicAuthError(Exception):
    """The credential is missing, unknown, revoked, disabled or expired."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def public_error_response(code: str, message: str, status_code: int, request_id: str) -> dict:
    """The stable /v1 envelope — deliberately not the internal {detail} shape."""
    type_by_code = {
        "invalid_api_key": "authentication_error",
        "key_disabled": "authentication_error",
        "key_expired": "authentication_error",
        "conversation_not_found": "not_found_error",
        "agent_unavailable": "permission_error",
        "agent_mismatch": "invalid_request_error",
        "rate_limit_exceeded": "rate_limit_error",
        "credit_limit_exceeded": "billing_error",
        "invalid_request": "invalid_request_error",
        "internal_error": "internal_error",
    }
    return {
        "status_code": status_code,
        "body": {
            "error": {
                "type": type_by_code.get(code, "internal_error"),
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
    }


def extract_bearer_key(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer mk_"):
        return None
    return header[len("Bearer "):]


async def get_api_key(
    request: Request, db: AsyncSession = Depends(get_db)
) -> ApiKey:
    presented = extract_bearer_key(request)
    if presented is None:
        raise PublicAuthError("invalid_api_key", "The API key provided is not valid.")
    key = (
        await db.execute(select(ApiKey).where(ApiKey.key_hash == hash_secret(presented)))
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if key is None or key.revoked_at is not None:
        raise PublicAuthError("invalid_api_key", "The API key provided is not valid.")
    if key.disabled_at is not None:
        raise PublicAuthError("key_disabled", "This API key has been disabled.")
    if key.expires_at is not None and key.expires_at <= now:
        raise PublicAuthError("key_expired", "This API key has expired.")

    # Truthful "last used" without a write per request: only the first call
    # inside the throttle interval touches the row.
    if key.last_used_at is None or (now - key.last_used_at).total_seconds() >= _LAST_USED_THROTTLE_S:
        key.last_used_at = now
        await db.commit()
    request.state.request_id = f"req_{uuid.uuid4().hex[:16]}"
    return key
