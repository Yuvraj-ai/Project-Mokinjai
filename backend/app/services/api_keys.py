"""API key lifecycle service (the 2026-11-05 api-keys design).

Generation, hashing, creation with one-time plaintext, lazy spend windows,
and the audit trail. The routers own the HTTP; this module owns the rules.
"""

import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import logger
from app.models.api_key import ApiKey, AuditLog
from app.models.execution import Execution
from app.services.sessions import hash_secret

_KEY_BYTES = 32  # 256 bits of CSPRNG output
_KEY_PREFIX = "mk_"
AUDIT_RESOURCE_TYPE = "api_key"

# How the reset period maps to a window length. The anchor rolls lazily at
# check time — a daily window that elapsed weeks ago rolls once, on the next
# request, with no cron.
_RESET_PERIODS: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
}

# Valid reset period values the API accepts (None = lifetime total).
RESET_PERIODS = tuple(_RESET_PERIODS)


def generate_api_key() -> str:
    """`mk_` + 256 bits of CSPRNG. The prefix makes a leaked key greppable."""
    return _KEY_PREFIX + secrets.token_urlsafe(_KEY_BYTES)


async def create_key(
    db: AsyncSession,
    *,
    workspace_id: str,
    user_id: str,
    name: str,
    expires_at: datetime | None = None,
    credit_limit_usd: Decimal | None = None,
    credit_reset_period: str | None = None,
    description: str | None = None,
) -> tuple[ApiKey, str]:
    """Create the row and return it with the plaintext — shown exactly once."""
    plaintext = generate_api_key()
    key = ApiKey(
        workspace_id=workspace_id,
        name=name,
        key_hash=hash_secret(plaintext),
        prefix=plaintext[: len(_KEY_PREFIX) + 6],
        description=description,
        created_by=user_id,
        expires_at=expires_at,
        credit_limit_usd=credit_limit_usd,
        credit_reset_period=credit_reset_period,
        spend_window_started_at=datetime.now(timezone.utc),
    )
    db.add(key)
    await db.flush()
    await audit(db, workspace_id, "created", key, {"name": name})
    return key, plaintext


async def audit(
    db: AsyncSession,
    workspace_id: str,
    action: str,
    key: ApiKey,
    extra: dict | None = None,
) -> None:
    """One audit row per key lifecycle event — never per invocation."""
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            action=action,
            resource_type=AUDIT_RESOURCE_TYPE,
            resource_id=key.id,
            metadata_={"prefix": key.prefix, "name": key.name, **(extra or {})},
        )
    )


async def rotate_key(db: AsyncSession, key: ApiKey, user_id: str) -> str:
    """Mint a new plaintext for the SAME row and return it exactly once.

    The old hash is replaced, so the old secret stops working the instant the
    request returns; the row (and its history) survives."""
    plaintext = generate_api_key()
    key.key_hash = hash_secret(plaintext)
    key.prefix = plaintext[: len(_KEY_PREFIX) + 6]
    key.revoked_at = None
    key.disabled_at = None
    await audit(db, key.workspace_id, "rotated", key)
    return plaintext


async def spend_in_window(db: AsyncSession, key: ApiKey) -> Decimal:
    """Spend for the key's current window, rolling the window lazily.

    Spend is SUM(executions.cost_usd) since the window anchor. If the reset
    period has elapsed, the anchor moves to now first — so an old window's
    spend is never counted against the new one — and only the roll writes."""
    now = datetime.now(timezone.utc)
    period = key.credit_reset_period
    if period and key.spend_window_started_at is not None:
        window_length = _RESET_PERIODS.get(period)
        if window_length is not None and now - key.spend_window_started_at >= window_length:
            key.spend_window_started_at = now
            await db.commit()

    query = (
        select(func.coalesce(func.sum(Execution.cost_usd), 0))
        .where(
            Execution.api_key_id == key.id,
            Execution.status == "completed",
        )
    )
    if key.spend_window_started_at is not None:
        query = query.where(Execution.created_at >= key.spend_window_started_at)
    total = (await db.execute(query)).scalar_one()
    return Decimal(str(total or 0))


__all__ = [
    "RESET_PERIODS",
    "audit",
    "create_key",
    "generate_api_key",
    "hash_secret",
    "rotate_key",
    "spend_in_window",
]
