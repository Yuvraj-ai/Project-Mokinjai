from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ProviderName = Literal["openai", "anthropic", "gemini", "custom"]


class LlmProfileTestRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider: ProviderName
    model_id: str = Field(min_length=1, max_length=255)
    api_key: str = ""
    base_url: str | None = None
    context_window: int | None = Field(default=None, gt=0)
    compaction_at_tokens: int | None = Field(default=None, gt=0)
    input_price_per_million: float = Field(ge=0)
    output_price_per_million: float = Field(ge=0)
    cache_price_per_million: float = Field(ge=0)
    profile_id: str | None = None


class LlmProfileResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    provider: str
    model_id: str
    base_url: str | None
    context_window: int
    compaction_at_tokens: int
    input_price_per_million: float
    output_price_per_million: float
    cache_price_per_million: float
    status: str
    last_error: str | None
    has_api_key: bool
    usable: bool
    created_at: datetime
    updated_at: datetime


class LlmProfileListResponse(BaseModel):
    profiles: list[LlmProfileResponse]
    total: int


class ContextWindowLookup(BaseModel):
    known: bool
    max_input_tokens: int | None
