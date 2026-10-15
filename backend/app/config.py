from pathlib import Path

from pydantic_settings import BaseSettings
from functools import lru_cache

# Resolve .env from the repository root, not the process CWD. pydantic-settings
# resolves a relative env_file against the CWD, so the same `cd backend` that
# every documented command uses silently skipped the real .env and fell back to
# the defaults below. Alembic (backend/alembic/env.py) resolves .env by its own
# absolute path; both now point at this same repo-root file, so the app and
# Alembic agree on one database.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agentbuilder"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM Providers
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""


    # Fernet key for LLM and MCP secrets at rest. Generate with Fernet.generate_key().
    LLM_ENCRYPTION_KEY: str = ""
    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ADMIN_CHAT_ID: str = ""

    # OTP
    OTP_EXPIRY_SECONDS: int = 300

    # App
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = {"env_file": ENV_FILE, "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
