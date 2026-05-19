from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Literal

WorkspaceRole = Literal["owner", "admin", "editor", "viewer"]
AssignableWorkspaceRole = Literal["admin", "editor", "viewer"]

class WorkspaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)

class WorkspaceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class MemberAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str
    role: AssignableWorkspaceRole = "viewer"

class MemberResponse(BaseModel):
    workspace_id: str
    user_id: str
    role: WorkspaceRole
    user_email: str | None = None
    user_name: str | None = None

    model_config = {"from_attributes": True}
