"""Workspace-scoped imports: one file per request, synchronously.

Synchronous on purpose: a background task cannot say which file failed, and there is
no job table to poll. Bounded by the upload ceiling, so no worker is needed at demo
scale. shortcut: revisit only if imports must survive a restart.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.services import cloud_connections as connection_store
from app.services import google_drive, onedrive
from app.services.document_import import import_document
from app.services.uploads import ALLOWED_UPLOAD_MIME_TYPES, normalise_content_type
from app.utils.errors import (
    BadRequestException,
    ConflictException,
    PayloadTooLargeException,
)

router = APIRouter()


class OneDriveImportIn(BaseModel):
    """An id only. Name, size and MIME come from Graph, never from this body."""

    item_id: str


class GoogleImportIn(BaseModel):
    """The picked id and a short-lived token. Name, size and MIME come from Drive."""

    file_id: str
    access_token: str


@router.post("/onedrive")
async def import_from_onedrive(
    payload: OneDriveImportIn,
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    connection = await connection_store.get_connection(
        db, user_id=current_user.id, provider="onedrive"
    )
    if connection is None:
        raise ConflictException("Connect OneDrive first")

    try:
        access = await onedrive.access_token_for(db, connection)
        metadata = await onedrive.get_item_metadata(access, payload.item_id)
    except onedrive.OneDriveAuthError:
        raise ConflictException("Reconnect OneDrive")

    if metadata["is_folder"]:
        raise BadRequestException("Choose files, not folders")
    limit = get_settings().STORAGE_MAX_UPLOAD_BYTES
    if metadata["size"] is not None and metadata["size"] > limit:
        raise PayloadTooLargeException(f"File exceeds the {limit} byte limit")

    declared = metadata["mime_type"] or ""
    normalised = normalise_content_type(declared)
    if normalised not in ALLOWED_UPLOAD_MIME_TYPES:
        raise BadRequestException(
            f"Unsupported file type {normalised or '(none)'}; accepted types are "
            f"{', '.join(sorted(ALLOWED_UPLOAD_MIME_TYPES))}"
        )

    data = bytearray()
    try:
        async for chunk in onedrive.download_item(access, payload.item_id):
            if len(data) + len(chunk) > limit:
                raise PayloadTooLargeException(f"File exceeds the {limit} byte limit")
            data.extend(chunk)
    except onedrive.OneDriveAuthError:
        raise ConflictException("Reconnect OneDrive")

    document, created = await import_document(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        provider="onedrive",
        source_id=payload.item_id,
        filename=metadata["name"],
        declared_content_type=declared,
        data=bytes(data),
    )
    return JSONResponse(
        status_code=201 if created else 200,
        content={
            "document_id": document.id,
            "filename": document.filename,
            "duplicate": not created,
        },
    )


@router.post("/google")
async def import_from_google(
    payload: GoogleImportIn,
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    try:
        metadata = await google_drive.get_file_metadata(
            payload.file_id, payload.access_token
        )
    except google_drive.GoogleDriveAuthError as exc:
        raise ConflictException(str(exc))

    source_mime = metadata["mime_type"] or ""
    exported = google_drive.export_mime(source_mime)
    if source_mime.startswith("application/vnd.google-apps.") and exported is None:
        raise BadRequestException(f"Cannot import Google type {source_mime}")
    resolved = exported or source_mime
    normalised = normalise_content_type(resolved)
    if normalised not in ALLOWED_UPLOAD_MIME_TYPES:
        raise BadRequestException(
            f"Unsupported file type {normalised or '(none)'}; accepted types are "
            f"{', '.join(sorted(ALLOWED_UPLOAD_MIME_TYPES))}"
        )
    limit = get_settings().STORAGE_MAX_UPLOAD_BYTES
    if metadata["size"] is not None and metadata["size"] > limit:
        raise PayloadTooLargeException(f"File exceeds the {limit} byte limit")

    try:
        data = await google_drive.download(
            payload.file_id, source_mime, payload.access_token
        )
    except google_drive.GoogleDriveAuthError as exc:
        raise ConflictException(str(exc))

    # An exported native file must carry its export extension in the name both the
    # library and the sandbox mount show.
    extension = (google_drive.export_extension(source_mime) or "") if exported else ""
    filename = metadata["name"] + extension
    document, created = await import_document(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
        provider="google",
        source_id=payload.file_id,
        filename=filename,
        declared_content_type=normalised,
        data=data,
    )
    return JSONResponse(
        status_code=201 if created else 200,
        content={
            "document_id": document.id,
            "filename": document.filename,
            "duplicate": not created,
        },
    )
