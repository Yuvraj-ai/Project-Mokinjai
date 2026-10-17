from datetime import datetime

from pydantic import BaseModel


class ExternalDatabaseCreate(BaseModel):
    name: str
    kind: str
    uri: str
    database_name: str | None = None
    collection_name: str | None = None


class ExternalDatabaseUpdate(BaseModel):
    """A partial update. An omitted field is unchanged; an explicit empty string clears
    a visible field. `uri` is the exception — blank keeps the stored ciphertext, because
    a secret that can never be read back cannot be edited by echo."""

    name: str | None = None
    kind: str | None = None
    uri: str | None = None
    database_name: str | None = None
    collection_name: str | None = None


class ExternalDatabaseResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    kind: str
    database_name: str | None = None
    collection_name: str | None = None
    has_uri: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExternalDatabaseListResponse(BaseModel):
    connections: list[ExternalDatabaseResponse]
    total: int
