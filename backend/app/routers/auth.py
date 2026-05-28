from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.logging import logger
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest
from app.schemas.otp import OTPSendResponse, OTPValidateRequest, OTPValidateResponse
from app.schemas.user import UserResponse
from app.utils.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.utils.errors import UnauthorizedException, OTPException
from app.config import get_settings
from app.middleware.auth import get_current_user
from app.services.otp_store import otp_store
from app.services.telegram import send_telegram_message

settings = get_settings()

router = APIRouter()


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


@router.post("/admin/otp/send", response_model=OTPSendResponse)
async def admin_send_otp(db: AsyncSession = Depends(get_db)):
    """Generate a 6-digit OTP and send it to the Telegram admin chat."""
    logger.info("Admin OTP requested — generating OTP")

    # Verify admin user exists
    result = await db.execute(select(User).where(User.is_superuser == True))
    admin_user = result.scalar_one_or_none()
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
    request: OTPValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate the OTP and return JWT tokens for the admin user."""
    logger.info("Admin OTP validation attempt")

    valid = otp_store.validate(request.session_token, request.code)
    if not valid:
        logger.warning("Admin OTP validation failed — invalid or expired code")
        raise OTPException(status_code=401, detail="Invalid or expired OTP")

    result = await db.execute(select(User).where(User.is_superuser == True))
    admin_user = result.scalar_one_or_none()
    if admin_user is None:
        raise OTPException(status_code=500, detail="Admin user not configured")

    token_data = {"sub": admin_user.id, "email": admin_user.email}
    access = create_access_token(token_data)
    refresh = create_refresh_token(token_data)

    logger.info(f"Admin login successful via OTP: {admin_user.id}")
    return OTPValidateResponse(
        access_token=access,
        refresh_token=refresh,
    )
