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

    # Object storage (ADR-011). Empty credentials select the filesystem backend; a
    # complete S3 credential set selects object storage. Resolved by
    # app/services/storage/__init__.py:get_storage() and read nowhere else, so the
    # selection rule has exactly one home.
    STORAGE_LOCAL_PATH: str = str(Path(__file__).resolve().parents[1] / "storage")
    STORAGE_S3_BUCKET: str = ""
    STORAGE_S3_ENDPOINT_URL: str = ""
    STORAGE_S3_REGION: str = "us-east-1"
    STORAGE_S3_ACCESS_KEY_ID: str = ""
    STORAGE_S3_SECRET_ACCESS_KEY: str = ""

    # Upload ceiling, enforced while reading the body (Task 5). A handler limit, not a
    # transport limit: see the spec's section 3.
    STORAGE_MAX_UPLOAD_BYTES: int = 25 * 1024 * 1024

    model_config = {"env_file": ENV_FILE, "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
