from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.logging import logger
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest
from app.schemas.user import UserResponse
from app.utils.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.utils.errors import BadRequestException, UnauthorizedException
from app.middleware.auth import get_current_user

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    logger.info(f"Registration attempt for email: {request.email}")
    result = await db.execute(select(User).where(User.email == request.email))
    existing = result.scalar_one_or_none()
    if existing:
        logger.warning(f"Registration failed — email already registered: {request.email}")
        raise BadRequestException("Email already registered")

    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
        name=request.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token_data = {"sub": user.id, "email": user.email}
    logger.info(f"User registered: {user.id} ({user.email})")
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    logger.info(f"Login attempt for email: {request.email}")
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(request.password, user.hashed_password):
        logger.warning(f"Login failed — invalid credentials for: {request.email}")
        raise UnauthorizedException("Invalid email or password")

    token_data = {"sub": user.id, "email": user.email}
    logger.info(f"Login successful: {user.id} ({user.email})")
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    logger.debug("Token refresh attempt")
    payload = decode_token(request.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        logger.warning("Token refresh failed — invalid refresh token")
        raise UnauthorizedException("Invalid refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"Token refresh failed — user {user_id} not found")
        raise UnauthorizedException("User not found")

    token_data = {"sub": user.id, "email": user.email}
    logger.info(f"Token refreshed for user: {user.id}")
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    logger.debug(f"User profile requested: {current_user.id}")
    return current_user
