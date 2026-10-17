from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
    # The model's attribute is `metadata_`; `from_attributes` cannot map that to
    # `metadata`, so the router builds this response explicitly. `file_url` (the storage
    # key), `content` and `vector_ids` are deliberately not exposed.
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
