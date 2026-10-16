from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CatalogEntryResponse(BaseModel):
    id: str
    display_name: str
    description: str
    transport: str
    auth_type: str
    secret_label: str | None
    config_fields: list[str]
    docs_url: str | None


class CatalogResponse(BaseModel):
    entries: list[CatalogEntryResponse]
    total: int


class ConnectorCreate(BaseModel):
    # `extra="forbid"` so an undeclared key is refused by name rather than ignored.
    # There is deliberately no `auth_scope`: Model B is not built, and a field with
    # one legal value is a field somebody will eventually set wrongly.
    model_config = ConfigDict(extra="forbid")

    connector_type: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    auth_secret: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class ConnectorUpdate(BaseModel):
    # No `connector_type`: a credential is meaningful only for the endpoint and auth
    # header of the type it was entered for, so changing the type would reinterpret it.
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    auth_secret: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class ConnectorResponse(BaseModel):
    """Every field a caller may see. There is no field for the ciphertext or the
    plaintext, so a secret cannot be serialised by building one of these."""

    id: str
    workspace_id: str
    connector_type: str
    display_name: str
    name: str
    transport: str
    auth_type: str
    auth_scope: str
    status: str
    has_auth: bool
    config: dict[str, Any]
    tools: list[str]
    last_error: str | None
    last_tested_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ConnectorListResponse(BaseModel):
    connectors: list[ConnectorResponse]
    total: int
