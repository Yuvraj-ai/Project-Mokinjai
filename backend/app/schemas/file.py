"""The workspace file library's request and response shapes.

Names are trimmed in the router, not here, so the error can name the field. The shapes
carry no storage key and no bytes: `file_url` is an internal detail.
"""

from datetime import datetime

from pydantic import BaseModel, Field

FOLDER_NAME_MAX = 255


class FolderCreate(BaseModel):
    # Length is checked in the router, so an empty or over-long name is the same 400 as
    # any other bad input rather than Pydantic's 422.
    name: str


class FolderRename(BaseModel):
    name: str


class FolderItem(BaseModel):
    id: str
    name: str
    file_count: int
    created_at: datetime


class FolderListResponse(BaseModel):
    folders: list[FolderItem]
    total: int


class FileItem(BaseModel):
    id: str
    filename: str | None
    file_size: int | None
    mime_type: str | None
    folder_id: str | None
    attached_agent_count: int
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[FileItem]
    total: int


class MoveDocumentsRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1)
    folder_id: str | None = None


class FolderForceDelete(BaseModel):
    confirm_name: str
