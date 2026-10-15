"""Server-side sessions.

A refresh token is valid only while its `sessions` row is unrevoked and unexpired,
which is what lets logout end a session instead of merely clearing a browser.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.logging import logger
from app.models.session import Session

settings = get_settings()

DEFAULT_MAX_SESSIONS = 3
_REFRESH_TOKEN_BYTES = 32  # 256 bits


def new_refresh_token() -> str:
    """An opaque refresh token. Opaque because the row, not the token, is authority."""
    return secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 of a refresh token.

    A plain digest rather than a slow KDF: the token is 256 bits of CSPRNG output,
    so there is no low-entropy guess to slow down.
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    db: AsyncSession,
    *,
    user_id: str,
    refresh_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
    max_sessions: int = DEFAULT_MAX_SESSIONS,
) -> Session:
    """Record a new session, evicting the oldest if the cap is reached."""
    # Serialise concurrent logins for this user. Without it two logins can both
    # read the same count, both conclude they are the last allowed, and both
    # insert. The advisory lock is transaction-scoped, so it releases on commit
    # or rollback without an error path having to clean it up.
    await db.execute(
        text("select pg_advisory_xact_lock(hashtext('mokinjay.sessions'), hashtext(:uid))"),
        {"uid": user_id},
    )

    now = datetime.now(timezone.utc)

    live = (
        await db.execute(
            select(Session)
            .where(
                Session.user_id == user_id,
                Session.revoked_at.is_(None),
                Session.expires_at > now,
            )
            .order_by(Session.last_used_at)
        )
    ).scalars().all()

    # Keep only enough room for the session about to be added.
    for stale in live[: max(0, len(live) - (max_sessions - 1))]:
        stale.revoked_at = now
        logger.info(f"Evicted oldest session {stale.id} for user {user_id} (cap {max_sessions})")

    session = Session(
        user_id=user_id,
        token_hash=hash_token(refresh_token),
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_live_session(db: AsyncSession, refresh_token: str) -> Session | None:
    """The session this refresh token belongs to, if it is still usable."""
    result = await db.execute(
        select(Session).where(
            Session.token_hash == hash_token(refresh_token),
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.scalar_one_or_none()


async def revoke_session(db: AsyncSession, session: Session) -> None:
    """End one session. The row is kept so the logout leaves a trace."""
    session.revoked_at = datetime.now(timezone.utc)
    await db.commit()


async def revoke_all_sessions(db: AsyncSession, user_id: str) -> int:
    """End every live session for a user. Returns how many were ended."""
    now = datetime.now(timezone.utc)
    live = (
        await db.execute(
            select(Session).where(
                Session.user_id == user_id,
                Session.revoked_at.is_(None),
                Session.expires_at > now,
            )
        )
    ).scalars().all()

    for session in live:
        session.revoked_at = now
    await db.commit()
    return len(live)


async def prune_expired_sessions(db: AsyncSession, retention_days: int = 30) -> int:
    """Delete sessions that expired longer ago than the retention window.

    Scheduling is deliberately left to deployment: there is no Celery beat
    schedule configured, and inventing one here would be infrastructure this
    change does not need.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    stale = (
        await db.execute(select(Session).where(Session.expires_at < cutoff))
    ).scalars().all()

    for session in stale:
        await db.delete(session)
    await db.commit()
    return len(stale)
