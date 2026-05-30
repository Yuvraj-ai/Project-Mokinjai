from pydantic import BaseModel
from datetime import datetime


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


class PromptListResponse(BaseModel):
    prompts: list[PromptResponse]
    total: int
