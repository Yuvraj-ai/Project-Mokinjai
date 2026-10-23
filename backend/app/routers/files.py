"""The workspace file library: flat folders, loose files, and their bytes.

A folder holds files only (spec, "Folder depth: level 1 now"). Deleting is the one
destructive path, so it is deliberate: a non-empty folder needs `force` and its exact
name, and a file attached to an agent is refused even then.
"""

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.logging import logger
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.models.agent import AgentDocument
from app.models.knowledge import DOCUMENT_STATUS_STORED, Document, FileFolder
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.file import (
    FOLDER_NAME_MAX,
    DocumentListResponse,
    FileItem,
    FolderCreate,
    FolderForceDelete,
    FolderItem,
    FolderListResponse,
    FolderRename,
    MoveDocumentsRequest,
)
from app.services.storage import (
    ObjectNotFoundError,
    StorageBackend,
    StorageError,
    build_storage_key,
    get_storage,
)
from app.utils.errors import (
    AppException,
    BadRequestException,
    ConflictException,
    NotFoundException,
    PayloadTooLargeException,
)

router = APIRouter()

# Extraction's input contract, declared here so an unsupported file is refused at upload
# rather than discovered later. These are the types the sandbox libraries (pypdf,
# python-docx, openpyxl, pandas) can read. PPTX and HTML are deferred.
ALLOWED_UPLOAD_MIME_TYPES = frozenset(
    {
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/json",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
)

UPLOAD_CHUNK_BYTES = 1024 * 1024


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _normalise_content_type(raw: str | None) -> str:
    """The declared type without parameters, lower-cased."""
    return (raw or "").split(";", 1)[0].strip().lower()


def _safe_filename(raw: str | None, document_id: str) -> str:
    """The client's filename with every path component removed.

    Not a storage defence — the key has no filename in it — but the name is what the
    download header and the sandbox mount use, so `..` and separators must not survive.
    """
    name = Path(raw.replace("\\", "/")).name if raw else ""
    return name[:255] or document_id


def _header_safe_filename(name: str) -> str:
    """A filename that cannot terminate its own Content-Disposition parameter."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    return cleaned or "download"


def _clean_name(raw: str) -> str:
    name = raw.strip()
    if not name:
        raise BadRequestException("A folder name cannot be empty")
    if len(name) > FOLDER_NAME_MAX:
        raise BadRequestException(f"A folder name cannot exceed {FOLDER_NAME_MAX} characters")
    return name


def _file_item(row: Document, attached_agent_count: int) -> FileItem:
    return FileItem(
        id=row.id,
        filename=row.filename,
        file_size=row.file_size,
        mime_type=row.mime_type,
        folder_id=row.folder_id,
        attached_agent_count=attached_agent_count,
        created_at=row.created_at,
    )


async def _folder_or_404(db: AsyncSession, workspace_id: str, folder_id: str) -> FileFolder:
    row = (
        await db.execute(
            select(FileFolder).where(
                FileFolder.id == folder_id, FileFolder.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundException("Folder")
    return row


async def _document_or_404(db: AsyncSession, workspace_id: str, document_id: str) -> Document:
    row = (
        await db.execute(
            select(Document).where(
                Document.id == document_id, Document.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundException("File")
    return row


def _attached_count():
    """Correlated count of the agents that hold one file."""
    return (
        select(func.count())
        .select_from(AgentDocument)
        .where(AgentDocument.document_id == Document.id)
        .correlate(Document)
        .scalar_subquery()
    )


# --------------------------------------------------------------------------- #
# folders
# --------------------------------------------------------------------------- #


@router.get("/folders", response_model=FolderListResponse)
async def list_folders(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    file_count = (
        select(func.count())
        .select_from(Document)
        .where(Document.folder_id == FileFolder.id)
        .correlate(FileFolder)
        .scalar_subquery()
    )
    rows = (
        await db.execute(
            select(FileFolder, file_count.label("file_count"))
            .where(FileFolder.workspace_id == workspace_id)
            .order_by(func.lower(FileFolder.name), FileFolder.id)
        )
    ).all()
    return FolderListResponse(
        folders=[
            FolderItem(
                id=folder.id,
                name=folder.name,
                file_count=count,
                created_at=folder.created_at,
            )
            for folder, count in rows
        ],
        total=len(rows),
    )


@router.post("/folders", response_model=FolderItem, status_code=201)
async def create_folder(
    workspace_id: str,
    request: FolderCreate,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    name = _clean_name(request.name)
    folder = FileFolder(workspace_id=workspace_id, name=name)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return FolderItem(id=folder.id, name=folder.name, file_count=0, created_at=folder.created_at)


@router.patch("/folders/{folder_id}", response_model=FolderItem)
async def rename_folder(
    workspace_id: str,
    folder_id: str,
    request: FolderRename,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    folder = await _folder_or_404(db, workspace_id, folder_id)
    folder.name = _clean_name(request.name)
    await db.commit()
    await db.refresh(folder)
    count = (
        await db.execute(
            select(func.count()).select_from(Document).where(Document.folder_id == folder.id)
        )
    ).scalar_one()
    return FolderItem(id=folder.id, name=folder.name, file_count=count, created_at=folder.created_at)


@router.delete("/folders/{folder_id}")
async def delete_folder(
    workspace_id: str,
    folder_id: str,
    force: bool = False,
    payload: FolderForceDelete | None = None,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    folder = await _folder_or_404(db, workspace_id, folder_id)
    documents = list(
        (
            await db.execute(select(Document).where(Document.folder_id == folder.id))
        )
        .scalars()
        .all()
    )

    if documents:
        document_ids = [row.id for row in documents]
        attached = (
            await db.execute(
                select(func.count())
                .select_from(AgentDocument)
                .where(AgentDocument.document_id.in_(document_ids))
            )
        ).scalar_one()
        if attached:
            raise ConflictException(
                f"{attached} file(s) in this folder are attached to agents; detach them first."
            )
        if not force:
            raise ConflictException(
                f"This folder contains {len(documents)} file(s). Move them to the root first, "
                "or delete the folder and its files."
            )
        if payload is None or payload.confirm_name != folder.name:
            raise BadRequestException("The folder name does not match")

    keys = [row.file_url for row in documents if row.file_url]
    for row in documents:
        await db.delete(row)
    await db.delete(folder)
    await db.commit()

    # Rows first, bytes second: a failed byte delete can only orphan an object.
    for key in keys:
        try:
            await get_storage().delete_file(key)
        except StorageError:
            logger.exception(f"Orphaned object left behind at {key!r}")
    logger.info(f"Folder {folder_id} deleted with {len(documents)} file(s)")
    return {"success": True}


# --------------------------------------------------------------------------- #
# documents
# --------------------------------------------------------------------------- #


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    workspace_id: str,
    folder_id: str | None = None,
    unfiled: bool = False,
    q: str | None = None,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    if folder_id and unfiled:
        raise BadRequestException("Choose a folder or unfiled files, not both")

    statement = select(Document, _attached_count().label("attached_agent_count")).where(
        Document.workspace_id == workspace_id
    )
    if folder_id:
        await _folder_or_404(db, workspace_id, folder_id)
        statement = statement.where(Document.folder_id == folder_id)
    elif unfiled:
        statement = statement.where(Document.folder_id.is_(None))
    if q:
        statement = statement.where(Document.filename.ilike(f"%{q}%"))

    rows = (await db.execute(statement.order_by(Document.created_at.desc()))).all()
    return DocumentListResponse(
        documents=[_file_item(row, count) for row, count in rows],
        total=len(rows),
    )


@router.post("/documents", response_model=FileItem, status_code=201)
async def upload_document(
    workspace_id: str,
    file: UploadFile = File(...),
    folder_id: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    if folder_id:
        await _folder_or_404(db, workspace_id, folder_id)

    declared = file.content_type or ""
    normalised = _normalise_content_type(declared)
    if normalised not in ALLOWED_UPLOAD_MIME_TYPES:
        raise BadRequestException(
            f"Unsupported file type {normalised or '(none)'}; accepted types are "
            f"{', '.join(sorted(ALLOWED_UPLOAD_MIME_TYPES))}"
        )

    payload = bytearray()
    max_upload_bytes = get_settings().STORAGE_MAX_UPLOAD_BYTES
    while True:
        chunk = await file.read(UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        if len(payload) + len(chunk) > max_upload_bytes:
            raise PayloadTooLargeException(f"File exceeds the {max_upload_bytes} byte limit")
        payload.extend(chunk)

    if not payload:
        raise BadRequestException("The uploaded file is empty")

    document_id = str(uuid.uuid4())
    key = build_storage_key(workspace_id, document_id)
    filename = _safe_filename(file.filename, document_id)
    storage = get_storage()

    try:
        await storage.upload_file(key, bytes(payload), content_type=normalised)
    except StorageError:
        # No row exists yet, so there is nothing to undo: the common failure case, and
        # the reason the bytes are written before the row.
        logger.exception(f"Storage write failed for workspace {workspace_id}")
        raise AppException(status_code=500, detail="The file could not be stored")

    document = Document(
        id=document_id,
        workspace_id=workspace_id,
        folder_id=folder_id,
        filename=filename,
        file_url=key,
        file_size=len(payload),
        mime_type=normalised,
        content=None,
        metadata_={
            "original_filename": filename,
            "uploaded_by": current_user.id,
            "declared_content_type": declared,
            "storage_backend": storage.name,
        },
        status=DOCUMENT_STATUS_STORED,
    )
    await _persist_document(db, storage, document)
    await db.refresh(document)

    # SEAM: text extraction does not happen here. Files reach the model through the
    # sandbox mount (docs/superpowers/specs/2026-10-16-knowledge-base-design.md §9);
    # `content` stays NULL by design and retrieval is the pending vector design.
    return _file_item(document, 0)


async def _persist_document(
    db: AsyncSession, storage: StorageBackend, document: Document
) -> None:
    """Insert the row, undoing the stored bytes if the commit fails."""
    db.add(document)
    try:
        await db.commit()
    except Exception:
        try:
            await storage.delete_file(document.file_url)
        except StorageError:
            logger.exception(f"Orphaned object left behind at {document.file_url!r}")
        raise


@router.patch("/documents")
async def move_documents(
    workspace_id: str,
    request: MoveDocumentsRequest,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    if request.folder_id:
        await _folder_or_404(db, workspace_id, request.folder_id)

    rows = list(
        (
            await db.execute(
                select(Document).where(
                    Document.workspace_id == workspace_id,
                    Document.id.in_(request.document_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    if len(rows) != len(set(request.document_ids)):
        raise NotFoundException("File")

    for row in rows:
        row.folder_id = request.folder_id
    await db.commit()
    return {"moved": len(rows)}


@router.delete("/documents/{document_id}")
async def delete_document(
    workspace_id: str,
    document_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    row = await _document_or_404(db, workspace_id, document_id)
    attached = (
        await db.execute(
            select(func.count())
            .select_from(AgentDocument)
            .where(AgentDocument.document_id == row.id)
        )
    ).scalar_one()
    if attached:
        raise ConflictException(f"This file is attached to {attached} agent(s); detach it first.")

    key = row.file_url
    await db.delete(row)
    await db.commit()

    if key:
        try:
            await get_storage().delete_file(key)
        except StorageError:
            logger.exception(f"Orphaned object left behind at {key!r}")
    return {"success": True}


@router.get("/documents/{document_id}/download")
async def download_document(
    workspace_id: str,
    document_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """The bytes, served by the backend. Downloading is a read, so a viewer may do it."""
    row = await _document_or_404(db, workspace_id, document_id)
    if not row.file_url:
        raise NotFoundException("Stored file")

    try:
        data = await get_storage().download_file(row.file_url)
    except ObjectNotFoundError:
        logger.error(f"Document {row.id} has no stored object at {row.file_url!r}")
        raise NotFoundException("Stored file")
    except StorageError:
        logger.exception(f"Storage read failed for document {row.id}")
        raise AppException(status_code=500, detail="The file could not be read")

    filename = _header_safe_filename(row.filename or row.id)
    return Response(
        content=data,
        media_type=row.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
