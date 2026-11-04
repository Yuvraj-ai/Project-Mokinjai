"""API key management schemas (plan Task 2)."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    expires_at: datetime | None = None
    credit_limit_usd: Decimal | None = Field(default=None, ge=0)
    credit_reset_period: Literal["daily", "weekly", "monthly"] | None = None
    description: str | None = Field(default=None, max_length=2000)


class ApiKeyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    credit_limit_usd: Decimal | None = Field(default=None, ge=0)
    credit_reset_period: Literal["daily", "weekly", "monthly"] | None = None
    description: str | None = Field(default=None, max_length=2000)


class ApiKeyResponse(BaseModel):
    """Never carries key_hash or plaintext — the prefix is the only trace."""

    id: str
    workspace_id: str
    name: str
    prefix: str
    description: str | None
    status: Literal["active", "revoked", "disabled", "expired"]
    credit_limit_usd: Decimal | None
    credit_reset_period: str | None
    spend_window_started_at: datetime | None
    created_at: datetime
    created_by: str
    expires_at: datetime | None
    last_used_at: datetime | None


class ApiKeyCreatedResponse(ApiKeyResponse):
    """The one response that carries the plaintext — shown exactly once."""

    key: str


class DailySpend(BaseModel):
    date: str
    cost: float


class ApiKeyUsageResponse(BaseModel):
    window_spend: float
    window_limit: float | None
    window_started_at: datetime | None
    totals: dict[str, float]  # today | week | month | total
    daily: list[DailySpend]  # last 30 days, ascending
