from pydantic import BaseModel
from datetime import datetime
from typing import Any


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None
    type: str = "document"
    config: dict[str, Any] = {}


class KnowledgeBaseResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None = None
    type: str
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: str
    knowledge_base_id: str
    filename: str | None = None
    file_size: int | None = None
    mime_type: str | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
