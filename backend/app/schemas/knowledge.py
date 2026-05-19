from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Any, Literal

KnowledgeBaseType = Literal["document", "url", "api"]
DocumentStatus = Literal["processing", "indexed", "failed"]

class KnowledgeBaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    type: KnowledgeBaseType = "document"
    config: dict[str, Any] = Field(default_factory=dict)

class KnowledgeBaseResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str | None = None
    type: KnowledgeBaseType
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
    status: DocumentStatus
    created_at: datetime

    model_config = {"from_attributes": True}
