"""The one writer for an imported file, shared by every provider.

Provider differences end at "we have bytes and a filename". This module applies the
same gate as the HTTP upload, writes the bytes before the row, and undoes the object if
the insert fails.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging import logger
from app.models.knowledge import DOCUMENT_STATUS_STORED, Document
from app.services.storage import StorageError, build_storage_key, get_storage
from app.services.uploads import (
    ALLOWED_UPLOAD_MIME_TYPES,
    enforce_size,
    normalise_content_type,
)
from app.utils.errors import AppException, BadRequestException


async def import_document(
    db: AsyncSession,
    *,
    workspace_id: str,
    user_id: str,
    provider: str,
    source_id: str,
    filename: str,
    declared_content_type: str,
    data: bytes,
) -> tuple[Document, bool]:
    """Store one provider file and insert one row. `created` is False on re-import."""
    normalised = normalise_content_type(declared_content_type)
    if normalised not in ALLOWED_UPLOAD_MIME_TYPES:
        raise BadRequestException(
            f"Unsupported file type {normalised or '(none)'}; accepted types are "
            f"{', '.join(sorted(ALLOWED_UPLOAD_MIME_TYPES))}"
        )
    enforce_size(len(data))

    existing = await _existing(db, workspace_id, provider, source_id)
    if existing is not None:
        return existing, False

    document_id = str(uuid.uuid4())
    key = build_storage_key(workspace_id, document_id)
    storage = get_storage()
    try:
        await storage.upload_file(key, data, content_type=normalised)
    except StorageError:
        logger.exception(f"Storage write failed for imported file in {workspace_id}")
        raise AppException(status_code=500, detail="The file could not be stored")

    document = Document(
        id=document_id,
        workspace_id=workspace_id,
        folder_id=None,
        filename=filename,
        file_url=key,
        file_size=len(data),
        mime_type=normalised,
        content=None,
        metadata_={
            "original_filename": filename,
            "uploaded_by": user_id,
            "declared_content_type": declared_content_type,
            "storage_backend": storage.name,
        },
        source_provider=provider,
        source_id=source_id,
        status=DOCUMENT_STATUS_STORED,
    )
    db.add(document)
    try:
        await db.commit()
    except IntegrityError:
        # The unique constraint caught a racing import. Its object is ours to remove.
        await db.rollback()
        await _delete_quietly(storage, key)
        existing = await _existing(db, workspace_id, provider, source_id)
        if existing is None:
            raise
        return existing, False
    except Exception:
        await _delete_quietly(storage, key)
        raise

    await db.refresh(document)
    return document, True


async def _existing(
    db: AsyncSession, workspace_id: str, provider: str, source_id: str
) -> Document | None:
    result = await db.execute(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.source_provider == provider,
            Document.source_id == source_id,
        )
    )
    return result.scalar_one_or_none()


async def _delete_quietly(storage, key: str) -> None:
    try:
        await storage.delete_file(key)
    except StorageError:
        logger.exception(f"Orphaned object left behind at {key!r}")
