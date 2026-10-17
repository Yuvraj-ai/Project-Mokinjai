import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# The kinds this table can hold. A tuple checked in the request schema, not a database
# ENUM: ADR-012 says "anything connectable via URI", and a fifth kind should be one
# entry here rather than a migration.
KINDS = ("postgres", "mysql", "mongodb", "chromadb")


class ExternalDatabaseConnection(Base):
    """A URI-addressable external database (ADR-012).

    The URI is a credential: Fernet-encrypted into `encrypted_uri`, never returned by any
    endpoint. `kind` names which target fields the record uses — it is a label for the UI
    and a validation input, never a driver selector, so nothing in this project imports a
    MySQL, Mongo or Chroma client.
    """

    __tablename__ = "external_database_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    encrypted_uri: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    database_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    collection_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace = relationship("Workspace", back_populates="external_database_connections")
