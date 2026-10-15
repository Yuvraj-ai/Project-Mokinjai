from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.logging import logger
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest
from app.schemas.otp import OTPSendResponse, OTPValidateRequest, OTPValidateResponse
from app.schemas.user import UserResponse
from app.utils.security import verify_password, create_access_token
from app.utils.errors import UnauthorizedException, OTPException
from app.config import get_settings
from app.middleware.auth import get_current_user
from app.services.otp_store import otp_store
from app.services.sessions import (
    create_session,
    get_live_session,
    new_refresh_token,
)
from app.services.telegram import send_telegram_message

settings = get_settings()

router = APIRouter()


async def _issue_tokens(db: AsyncSession, user: User, request: Request) -> TokenResponse:
    """Mint a session and the token pair for it.

    Every path that logs someone in must come through here. A token minted
    without a session authenticates normally and can never be revoked, which is
    the failure this whole change exists to prevent.
    """
    refresh_token = new_refresh_token()
    session = await create_session(
        db,
        user_id=user.id,
        refresh_token=refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    access_token = create_access_token(
        {"sub": user.id, "email": user.email, "sid": session.id}
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(request_body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    logger.info(f"Login attempt for email: {request_body.email}")
    result = await db.execute(select(User).where(User.email == request_body.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(request_body.password, user.hashed_password):
        logger.warning(f"Login failed — invalid credentials for: {request_body.email}")
        raise UnauthorizedException("Invalid email or password")

    logger.info(f"Login successful: {user.id} ({user.email})")
    return await _issue_tokens(db, user, request)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request_body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    logger.debug("Token refresh attempt")
    session = await get_live_session(db, request_body.refresh_token)
    if session is None:
        logger.warning("Token refresh failed — no live session for this token")
        raise UnauthorizedException("Invalid refresh token")

    user = await db.get(User, session.user_id)
    if user is None:
        logger.warning(f"Token refresh failed — user {session.user_id} not found")
        raise UnauthorizedException("User not found")

    # Only the access token is reissued: without rotation the refresh token stays
    # valid, and this write is what keeps `last_used_at` meaningful for eviction.
    # The commit is load-bearing. Without it the assignment is discarded when the
    # request's session closes, and eviction silently degrades from
    # least-recently-used to oldest-created.
    session.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    token_data = {"sub": user.id, "email": user.email, "sid": session.id}
    logger.info(f"Token refreshed for user: {user.id}")
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=request_body.refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    logger.debug(f"User profile requested: {current_user.id}")
    return current_user


@router.post("/admin/otp/send", response_model=OTPSendResponse)
async def admin_send_otp(db: AsyncSession = Depends(get_db)):
    """Generate a 6-digit OTP and send it to the Telegram admin chat."""
    logger.info("Admin OTP requested — generating OTP")

    # Verify admin user exists
    result = await db.execute(select(User).where(User.is_superuser == True))
    admin_user = result.scalars().first()
    if admin_user is None:
        logger.error("Admin OTP requested but no superuser exists in database")
        raise OTPException(status_code=500, detail="Admin user not configured")

    session_token, code = otp_store.generate()

    message = (
        f"🔐 <b>Admin Login OTP</b>\n\n"
        f"Your code: <code>{code}</code>\n\n"
        f"This code expires in 5 minutes."
    )
    sent = await send_telegram_message(message)
    if not sent:
        logger.error("Failed to send OTP to Telegram")
        raise OTPException(status_code=500, detail="Failed to send OTP. Check Telegram configuration.")

    logger.info("Admin OTP sent to Telegram")
    return OTPSendResponse(
        session_token=session_token,
        expires_in=settings.OTP_EXPIRY_SECONDS,
        message="OTP sent to admin Telegram",
    )


@router.post("/admin/otp/validate", response_model=OTPValidateResponse)
async def admin_validate_otp(
    request_body: OTPValidateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Validate the OTP and return JWT tokens for the admin user."""
    logger.info("Admin OTP validation attempt")

    valid = otp_store.validate(request_body.session_token, request_body.code)
    if not valid:
        logger.warning("Admin OTP validation failed — invalid or expired code")
        raise OTPException(status_code=401, detail="Invalid or expired OTP")

    result = await db.execute(select(User).where(User.is_superuser == True))
    admin_user = result.scalars().first()
    if admin_user is None:
        raise OTPException(status_code=500, detail="Admin user not configured")

    logger.info(f"Admin login successful via OTP: {admin_user.id}")
    tokens = await _issue_tokens(db, admin_user, request)
    return OTPValidateResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )
