"""Send messages to a Telegram chat via the Telegram Bot HTTP API."""

import httpx
from app.config import get_settings
from app.logging import logger

settings = get_settings()

TELEGRAM_API = "https://api.telegram.org"


async def send_telegram_message(text: str) -> bool:
    """Send a message to the configured Telegram admin chat.

    Returns True on success, False on failure.
    """
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        logger.error("Telegram not configured: TELEGRAM_BOT_TOKEN or TELEGRAM_ADMIN_CHAT_ID is empty")
        return False

    url = f"{TELEGRAM_API}/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("OTP sent to Telegram admin chat")
            return True
    except Exception as e:
        logger.error(f"Failed to send OTP to Telegram: {e}")
        return False
