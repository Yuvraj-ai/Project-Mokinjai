import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


# Document.status. This plan writes only STORED, and a document may stay there
# indefinitely: filling `content` is the Docker sandbox's job (Phase 2, ADR-010).
DOCUMENT_STATUS_STORED = "stored"
# Reserved, never written here: set by the extraction phase, and by the embedding job in
# docs/superpowers/specs/2026-10-16-vector-database-design.md section 2.
DOCUMENT_STATUS_INDEXED = "indexed"
DOCUMENT_STATUS_FAILED = "failed"
DOCUMENT_STATUSES = (DOCUMENT_STATUS_STORED, DOCUMENT_STATUS_INDEXED, DOCUMENT_STATUS_FAILED)


class FileFolder(Base):
    """One level of grouping over the workspace-wide file library.

    A folder holds files, never other folders (spec, "Folder depth: level 1 now").
    """

    __tablename__ = "file_folders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    workspace = relationship("Workspace", back_populates="file_folders")
    # No delete cascade and no FK nulling: the database RESTRICT and the folder-delete
    # service are the only paths that may remove a file, so a stray `db.delete(folder)`
    # fails loudly instead of destroying bytes (or silently orphaning them at the root).
    documents = relationship("Document", back_populates="folder", passive_deletes=True)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Required even for a folderless file: a root file has no folder to derive the
    # workspace from, and every read must be scoped.
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    folder_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("file_folders.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # The object-storage KEY from app.services.storage.build_storage_key — not a URL, not
    # user-supplied, and not exposed in any response. The name is historical.
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # SEAM: never written. Text extraction belongs to the Phase 2 Docker sandbox
    # (ADR-010) — see the SEAM note in app/routers/files.py, which names the spec
    # where this resumes.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Server-written provenance from the upload path: original_filename, uploaded_by,
    # declared_content_type, storage_backend. Never user input.
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    # PLACEHOLDER: vector store IDs. Type and semantics are undecided; see the
    # "Deferred: the vector database" section of
    # docs/superpowers/specs/2026-10-15-postgresql-only-design.md.
    # Nothing reads or writes this column. Do not build on it.
    vector_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    # One of DOCUMENT_STATUSES above. This plan writes DOCUMENT_STATUS_STORED only, and
    # there is no transition out of it here: extraction is Phase 2's (ADR-010), and
    # embedding is the vector plan's.
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    folder = relationship("FileFolder", back_populates="documents")
