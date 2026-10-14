from pydantic import BaseModel, computed_field
from datetime import datetime

from app.utils.tokens import count_tokens


class PromptCreate(BaseModel):
    name: str
    description: str | None = None
    content: str


class PromptUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None


class PromptResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None = None
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def token_count(self) -> int:
        return count_tokens(self.content)


class PromptListResponse(BaseModel):
    prompts: list[PromptResponse]
    total: int
