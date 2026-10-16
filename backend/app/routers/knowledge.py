import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.logging import logger
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.models.knowledge import DOCUMENT_STATUS_STORED, Document, KnowledgeBase
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.knowledge import (
    DocumentListResponse,
    DocumentResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
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
    NotFoundException,
    PayloadTooLargeException,
)

router = APIRouter()

# Only "document" is supported: a url knowledge base implies fetching and crawling, and
# an api knowledge base has no design at all. The set lives here rather than in a database
# constraint so widening it later needs no migration.
SUPPORTED_KNOWLEDGE_BASE_TYPES = ("document",)

# Extraction's input contract, declared here so an unsupported file is refused at upload
# rather than discovered in Phase 2. These are the types memory.md's sandbox libraries
# (pypdf, python-docx, openpyxl, pandas) can read. PPTX is deferred (PROJECT_STATUS.md).
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



@router.post("", response_model=KnowledgeBaseResponse)
async def create_knowledge_base(
    workspace_id: str,
    request: KnowledgeBaseCreate,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    if request.type not in SUPPORTED_KNOWLEDGE_BASE_TYPES:
        raise BadRequestException(
            f"Unsupported knowledge base type {request.type!r}. Only "
            f"{', '.join(repr(t) for t in SUPPORTED_KNOWLEDGE_BASE_TYPES)} is supported; "
            "'url' and 'api' have no design yet."
        )
    logger.info(f"Creating knowledge base '{request.name}' in workspace {workspace_id}")
    kb = KnowledgeBase(
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        type=request.type,
        config=request.config,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    logger.info(f"Knowledge base {kb.id} created")
    return kb


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    logger.debug(f"Listing knowledge bases for workspace {workspace_id}")
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.workspace_id == workspace_id)
        .order_by(KnowledgeBase.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    workspace_id: str,
    kb_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.workspace_id == workspace_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        logger.warning(f"Knowledge base {kb_id} not found in workspace {workspace_id}")
        raise NotFoundException("Knowledge base")
    return kb


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    workspace_id: str,
    kb_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    logger.info(f"Deleting knowledge base {kb_id}")
    kb = await _load_knowledge_base(db, workspace_id, kb_id)

    # Collect the keys before the rows go: after the commit there is nothing left to
    # tell us which objects belonged to this knowledge base.
    documents = (
        await db.execute(select(Document).where(Document.knowledge_base_id == kb_id))
    ).scalars().all()
    keys = [row.file_url for row in documents if row.file_url]

    await db.delete(kb)
    await db.commit()

    # Same ordering rule as a single document: rows first, bytes second, so a failure
    # here can only orphan objects.
    storage = get_storage()
    for key in keys:
        try:
            await storage.delete_file(key)
        except StorageError:
            logger.exception(f"Orphaned object left behind at {key!r}")

    logger.info(f"Knowledge base {kb_id} deleted with {len(keys)} stored object(s)")
    return {"success": True}



async def _load_knowledge_base(
    db: AsyncSession, workspace_id: str, kb_id: str
) -> KnowledgeBase:
    """The knowledge base, scoped to the workspace in the path."""
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.workspace_id == workspace_id,
        )
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        logger.warning(f"Knowledge base {kb_id} not found in workspace {workspace_id}")
        raise NotFoundException("Knowledge base")
    return kb


def _normalise_content_type(raw: str | None) -> str:
    """`text/plain; charset=utf-8` -> `text/plain`. Browsers always add the parameter."""
    if not raw:
        return ""
    return raw.split(";", 1)[0].strip().lower()


def _safe_filename(raw: str | None, document_id: str) -> str:
    """The client's filename as a stored label: basename only, capped, never empty.

    Windows clients send backslashes, which are not separators on POSIX, so they are
    normalised first. This is about legibility, not safety: the name never enters a
    storage key, and it is sanitised again before it enters a header.
    """
    name = Path(raw.replace("\\", "/")).name if raw else ""
    return name[:255] or document_id


def _to_document_response(row: Document) -> DocumentResponse:
    return DocumentResponse(
        id=row.id,
        knowledge_base_id=row.knowledge_base_id,
        filename=row.filename,
        file_size=row.file_size,
        mime_type=row.mime_type,
        status=row.status,
        metadata=row.metadata_ or {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _header_safe_filename(name: str) -> str:
    """A filename that cannot terminate its own Content-Disposition parameter.

    Quotes, backslashes and control characters in a client-supplied name would let it
    end the quoted parameter or the header. Anything outside a conservative set is
    replaced rather than escaped, because the value only needs to be recognisable.
    """
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    return cleaned or "download"


async def _load_document(db: AsyncSession, kb_id: str, document_id: str) -> Document:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.knowledge_base_id == kb_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        logger.warning(f"Document {document_id} not found in knowledge base {kb_id}")
        raise NotFoundException("Document")
    return row



async def _persist_document(
    db: AsyncSession, storage: StorageBackend, document: Document
) -> None:
    """Insert the row, undoing the stored bytes if the commit fails.

    The ordering is deliberate: bytes first, row second, so the only failure this code can
    leave behind is an object with no row — invisible and harmless — rather than a row
    with no object, which would be a 500 on download.
    """
    db.add(document)
    try:
        await db.commit()
    except Exception:
        try:
            await storage.delete_file(document.file_url)
        except StorageError:
            logger.exception(f"Orphaned object left behind at {document.file_url!r}")
        raise


@router.post("/{kb_id}/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    workspace_id: str,
    kb_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    await _load_knowledge_base(db, workspace_id, kb_id)

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
            raise PayloadTooLargeException(
                f"File exceeds the {max_upload_bytes} byte limit"
            )
        payload.extend(chunk)

    if not payload:
        raise BadRequestException("The uploaded file is empty")

    document_id = str(uuid.uuid4())
    key = build_storage_key(workspace_id, kb_id, document_id)
    filename = _safe_filename(file.filename, document_id)
    storage = get_storage()

    try:
        await storage.upload_file(key, bytes(payload), content_type=normalised)
    except StorageError:
        # No row exists yet, so there is nothing to undo: the common failure case, and
        # the reason the bytes are written before the row.
        logger.exception(f"Storage write failed for knowledge base {kb_id}")
        raise AppException(status_code=500, detail="The file could not be stored")

    document = Document(
        id=document_id,
        knowledge_base_id=kb_id,
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
    logger.info(
        f"Document {document.id} stored in knowledge base {kb_id} ({len(payload)} bytes)"
    )

    # SEAM: text extraction does not happen here, and this is not an oversight.
    # Filling Document.content is the Docker sandbox's job — a per-agent, Phase 2
    # capability (ADR-010, ADR-007), designed in memory.md under "Knowledge Base Sandbox
    # Design" and "Docker Sandbox Centralized Model". That spec is still owed;
    # docs/superpowers/specs/2026-10-16-tools-design.md section 7 names the interface it
    # must provide. Until it lands, `content` stays NULL and `status` stays "stored" —
    # possibly forever, which is a valid state and not a failure. Retrieval resumes at
    # docs/superpowers/specs/2026-10-16-vector-database-design.md section 4.

    return _to_document_response(document)


@router.get("/{kb_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    workspace_id: str,
    kb_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await _load_knowledge_base(db, workspace_id, kb_id)
    result = await db.execute(
        select(Document)
        .where(Document.knowledge_base_id == kb_id)
        .order_by(Document.created_at.desc())
    )
    rows = list(result.scalars().all())
    return DocumentListResponse(
        documents=[_to_document_response(row) for row in rows], total=len(rows)
    )


@router.get("/{kb_id}/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    workspace_id: str,
    kb_id: str,
    document_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await _load_knowledge_base(db, workspace_id, kb_id)
    return _to_document_response(await _load_document(db, kb_id, document_id))


@router.get("/{kb_id}/documents/{document_id}/download")
async def download_document(
    workspace_id: str,
    kb_id: str,
    document_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """The bytes, served by the backend. Downloading is a read, so a viewer may do it."""
    await _load_knowledge_base(db, workspace_id, kb_id)
    row = await _load_document(db, kb_id, document_id)
    if not row.file_url:
        # Only reachable for a row that predates this plan. Every row this API creates
        # has a key.
        raise NotFoundException("Stored file")

    try:
        data = await get_storage().download_file(row.file_url)
    except ObjectNotFoundError:
        # The row is the index, so bytes that are missing are a real inconsistency.
        # Reported as 404 rather than 500: there is nothing for a retry to fix.
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


@router.delete("/{kb_id}/documents/{document_id}")
async def delete_document(
    workspace_id: str,
    kb_id: str,
    document_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    await _load_knowledge_base(db, workspace_id, kb_id)
    row = await _load_document(db, kb_id, document_id)
    key = row.file_url

    await db.delete(row)
    await db.commit()

    # Row first, bytes second: a failed byte delete can only orphan an object, never
    # leave a row pointing at nothing.
    if key:
        try:
            await get_storage().delete_file(key)
        except StorageError:
            logger.exception(f"Orphaned object left behind at {key!r}")
    logger.info(f"Document {document_id} deleted")
    return {"success": True}


