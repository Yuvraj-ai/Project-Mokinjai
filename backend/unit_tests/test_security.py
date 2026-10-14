from datetime import datetime, timedelta, timezone
import pytest
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestPasswordHashing:
    def test_hash_password_returns_string(self):
        result = hash_password("mypassword")
        assert isinstance(result, str)

    def test_hash_password_differs_each_time(self):
        h1 = hash_password("mypassword")
        h2 = hash_password("mypassword")
        assert h1 != h2

    def test_verify_password_correct(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False


class TestAccessToken:
    def test_create_access_token_returns_string(self):
        token = create_access_token({"sub": "user123", "email": "test@test.com"})
        assert isinstance(token, str)

    def test_decode_access_token(self):
        token = create_access_token({"sub": "user123", "email": "test@test.com"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@test.com"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_decode_expired_token(self):
        from jose import jwt
        from app.config import get_settings

        settings = get_settings()
        expired_payload = {
            "sub": "user123",
            "email": "test@test.com",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "type": "access",
        }
        token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        result = decode_token(token)
        assert result is None

    def test_decode_invalid_token(self):
        result = decode_token("invalid.token.here")
        assert result is None


class TestRefreshToken:
    def test_create_refresh_token_returns_string(self):
        token = create_refresh_token({"sub": "user123", "email": "test@test.com"})
        assert isinstance(token, str)

    def test_decode_refresh_token(self):
        token = create_refresh_token({"sub": "user123", "email": "test@test.com"})
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_refresh_token_has_longer_expiry(self):
        access = create_access_token({"sub": "user123", "email": "test@test.com"})
        refresh = create_refresh_token({"sub": "user123", "email": "test@test.com"})
        access_payload = decode_token(access)
        refresh_payload = decode_token(refresh)
        assert refresh_payload["exp"] > access_payload["exp"]
