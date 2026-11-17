"""A user's connection to a cloud file provider.

Per user, not per workspace: the token belongs to the person who granted it, and a
workspace member list is not an identity provider. Only the refresh token is stored,
encrypted with the same key as connector secrets.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CloudConnection(Base):
    __tablename__ = "cloud_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_cloud_connections_user_provider"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # Display only; the provider's own id is never stored.
    account_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refresh_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
