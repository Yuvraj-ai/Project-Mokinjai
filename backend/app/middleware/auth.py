from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.logging import logger
from app.models.user import User
from app.utils.security import decode_token
from app.utils.errors import UnauthorizedException

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        logger.warning("Authentication failed — invalid or expired token")
        raise UnauthorizedException("Invalid or expired token")

    if payload.get("type") != "access":
        logger.warning(f"Authentication failed — invalid token type: {payload.get('type')}")
        raise UnauthorizedException("Invalid token type")

    user_id = payload.get("sub")
    if user_id is None:
        logger.warning("Authentication failed — no user ID in token payload")
        raise UnauthorizedException("Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"Authentication failed — user {user_id} not found in database")
        raise UnauthorizedException("User not found")

    logger.debug(f"Authenticated user: {user.id} ({user.email})")
    return user
