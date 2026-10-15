from datetime import datetime, timezone

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import logger
from app.models.session import Session
from app.models.user import User
from app.utils.errors import UnauthorizedException
from app.utils.security import decode_token

security = HTTPBearer()


async def _resolve_session_and_user(
    credentials: HTTPAuthorizationCredentials,
    db: AsyncSession,
) -> tuple[Session, User]:
    """Decode the access token and confirm its session is still alive.

    One query: the session join is added to the user lookup that already happened
    here, so per-request revocation costs no extra round trip.
    """
    payload = decode_token(credentials.credentials)
    if payload is None:
        logger.warning("Authentication failed — invalid or expired token")
        raise UnauthorizedException("Invalid or expired token")

    if payload.get("type") != "access":
        logger.warning(f"Authentication failed — invalid token type: {payload.get('type')}")
        raise UnauthorizedException("Invalid token type")

    session_id = payload.get("sid")
    if session_id is None:
        logger.warning("Authentication failed — token carries no session id")
        raise UnauthorizedException("Token is not tied to a session; sign in again")

    result = await db.execute(
        select(User, Session)
        .join(Session, Session.user_id == User.id)
        .where(
            Session.id == session_id,
            Session.revoked_at.is_(None),
            Session.expires_at > datetime.now(timezone.utc),
        )
    )
    row = result.first()
    if row is None:
        logger.warning(f"Authentication failed — session {session_id} is not usable")
        raise UnauthorizedException("Session has ended; sign in again")

    user, session = row
    return session, user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    _, user = await _resolve_session_and_user(credentials, db)
    logger.debug(f"Authenticated user: {user.id} ({user.email})")
    return user


async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Session:
    """The session behind the current request — what logout needs to revoke."""
    session, _ = await _resolve_session_and_user(credentials, db)
    return session
