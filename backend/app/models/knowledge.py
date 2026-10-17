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


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Only "document" is supported. "url" and "api" have no design and are refused by the
    # router; the column stays String(50) so widening the set again needs no migration.
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # document
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    workspace = relationship("Workspace", back_populates="knowledge_bases")
    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    knowledge_base_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # The object-storage KEY from app.services.storage.build_storage_key — not a URL, not
    # user-supplied, and not exposed in any response. The name is historical.
    file_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # SEAM: never written. Text extraction belongs to the Phase 2 Docker sandbox
    # (ADR-010) — see the SEAM note in app/routers/knowledge.py, which names the spec
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

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
