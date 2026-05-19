from typing import Literal
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    ENVIRONMENT: Literal["local", "test", "production"] = "local"
    
    # Database (SQLite)
    DATABASE_URL: str = "sqlite+aiosqlite:///./agentbuilder.db"
    
    # MongoDB Atlas (JSON Storage + Vector Search)
    MONGO_URL: str = ""
    MONGO_DB_NAME: str = "lane1"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    JWT_SECRET_KEY: SecretStr = Field(default=SecretStr("dev-only-change-me"))
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM Providers
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # App
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.ENVIRONMENT == "production":
            if self.JWT_SECRET_KEY.get_secret_value() in {
                "dev-only-change-me",
                "your-super-secret-key-change-in-production",
            }:
                raise ValueError("JWT_SECRET_KEY must be set in production")
            if not self.MONGO_URL:
                raise ValueError("MONGO_URL must be set in production")
        return self

@lru_cache()
def get_settings() -> Settings:
    return Settings()
