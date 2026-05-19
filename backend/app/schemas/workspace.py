from pydantic import BaseModel
from datetime import datetime


class WorkspaceCreate(BaseModel):
    name: str


class WorkspaceUpdate(BaseModel):
    name: str | None = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemberAdd(BaseModel):
    user_id: str
    role: str = "viewer"  # owner, admin, editor, viewer


class MemberResponse(BaseModel):
    workspace_id: str
    user_id: str
    role: str
    user_email: str | None = None
    user_name: str | None = None

    model_config = {"from_attributes": True}
