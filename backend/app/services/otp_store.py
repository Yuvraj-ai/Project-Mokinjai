"""In-memory OTP store with TTL.

Stores 6-digit codes per session (identified by a random token).
Each code expires after OTP_EXPIRY_SECONDS.
"""

import secrets
import time
from app.config import get_settings

settings = get_settings()


class _OTPStore:
    def __init__(self):
        self._codes: dict[str, dict] = {}

    def generate(self) -> tuple[str, str]:
        """Generate a new OTP. Returns (session_token, otp_code)."""
        session_token = secrets.token_urlsafe(32)
        code = secrets.randbelow(1_000_000)
        otp_code = f"{code:06d}"
        self._codes[session_token] = {
            "code": otp_code,
            "expires_at": time.time() + settings.OTP_EXPIRY_SECONDS,
            "attempts": 0,
        }
        return session_token, otp_code

    def validate(self, session_token: str, user_code: str) -> bool:
        """Validate a user-provided OTP. Returns True on success."""
        entry = self._codes.get(session_token)
        if entry is None:
            return False
        if time.time() > entry["expires_at"]:
            del self._codes[session_token]
            return False
        entry["attempts"] += 1
        if entry["attempts"] >= 5:
            del self._codes[session_token]
            return False
        if entry["code"] == user_code:
            del self._codes[session_token]
            return True
        return False

    def cleanup_expired(self):
        """Remove expired entries."""
        now = time.time()
        self._codes = {k: v for k, v in self._codes.items() if v["expires_at"] > now}


otp_store = _OTPStore()
