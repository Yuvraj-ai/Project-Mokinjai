"""Rate and credit limits for the public /v1 surface (plan Task 4).

Enforcement order on every request: auth → revoked/disabled → expiry →
credit limit → rate limit — all before any model call, so a refused request
never spends a token. The Redis limiter is a fixed window (INCR + EXPIRE,
two commands) and FAILS OPEN when Redis is unreachable: the product stays
up, the abuse window is logged loudly.
"""

import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging import logger
from app.middleware.public_auth import PublicAuthError
from app.models.api_key import ApiKey
from app.services.api_keys import spend_in_window

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
    return _redis


def check_rate_limit(key_id: str) -> dict[str, str]:
    """The fixed-window counter and its response headers. Raises 429 over the
    limit; returns the X-RateLimit-* headers either way."""
    settings = get_settings()
    limit = settings.PUBLIC_API_RATE_LIMIT_PER_MINUTE
    window = int(time.time() // 60)
    bucket = f"ratelimit:{key_id}:{window}"
    try:
        client = get_redis()
        count = client.incr(bucket)
        client.expire(bucket, 61)
    except Exception:
        logger.exception("Rate limiter could not reach Redis — failing OPEN")
        return {}

    headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(max(0, limit - count)),
        "X-RateLimit-Reset": str((window + 1) * 60),
    }
    if count > limit:
        retry_after = (window + 1) * 60 - int(time.time())
        raise PublicAuthError("rate_limit_exceeded", "Too many requests.")
    return headers


def _roll_window(key: ApiKey, now: datetime) -> bool:
    period = key.credit_reset_period
    if not period or key.spend_window_started_at is None:
        return False
    length = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1), "monthly": timedelta(days=30)}.get(period)
    if length is not None and now - key.spend_window_started_at >= length:
        key.spend_window_started_at = now
        return True
    return False


async def check_credit(db: AsyncSession, key: ApiKey) -> Decimal:
    """Spend vs the credit limit; raises 402 over budget. Unlimited (None)
    limits never raise, and the spend is still computed for the dashboard."""
    from app.services.api_keys import spend_in_window

    spend = await spend_in_window(db, key)
    if key.credit_limit_usd is not None and spend >= key.credit_limit_usd:
        raise PublicAuthError(
            "credit_limit_exceeded",
            f"This key has spent ${spend:.2f} of its ${key.credit_limit_usd:.2f} limit.",
        )
    return spend
