from typing import Literal

from pydantic import BaseModel, Field

SearchProvider = Literal["tavily", "exa"]


class SearchCredentialUpsert(BaseModel):
    api_key: str = Field(min_length=1)


class SearchCredentialResponse(BaseModel):
    provider: str
    has_key: bool
