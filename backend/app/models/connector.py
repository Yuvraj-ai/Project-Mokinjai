import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ConnectorInstance(Base):
    """One catalog connector, enabled in one workspace.

    `auth_encrypted` holds the Fernet ciphertext of the credential and is NULL
    exactly when the catalog entry's `auth_type` is "none" — an entry that takes no
    secret has none to store, and a zero-length blob would make every reader
    special-case it. `config` holds the non-secret values the entry declares.
    `tool_names` is the last successful probe's answer, persisted because finding it
    out costs a network call.

    `transport` is not a column: it is the catalog entry's property, and a stored
    copy would be a second source of truth that goes stale the first time an entry
    is corrected. `auth_scope` is ADR-020's migration point to Model B and is always
    "workspace" in this change.
    """

    __tablename__ = "connector_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    auth_scope: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'workspace'")
    )
    auth_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    tool_names: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    workspace = relationship("Workspace", back_populates="connector_instances")
