"""Playground chat persistence (spec §4, plan Task 1).

A session is a server-owned thread: the client sends only the new message and
history is loaded from these rows. The assistant message's `activity` JSONB is
the ordered event log for the turn — the same objects the SSE stream emitted —
so a replayed session renders exactly as the live one did.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, Sequence, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Global monotonic tiebreak for message ordering (plan Task 3's replay contract).
# `created_at` cannot order rows inserted in one transaction — Postgres `now()` is
# transaction-scoped, so a turn's user and assistant rows share a timestamp — and
# the uuid4 PK does not order. The sequence is global, not per-session, which is
# fine: within one session its values are still strictly increasing by insert.
CHAT_MESSAGE_SEQ = Sequence("chat_messages_seq_seq", metadata=Base.metadata)


class ChatSession(Base):
    """One playground thread for one agent (spec P1: server-persisted)."""

    __tablename__ = "chat_sessions"
    __table_args__ = (Index("ix_chat_sessions_workspace_updated", "workspace_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Set when the session was created through the public /v1 surface: a key
    # may only read and append to sessions it created (exfiltration guard).
    api_key_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New session")
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ChatMessage(Base):
    """One turn's user or assistant row (spec §4).

    `reasoning`, `activity`, `structured`, `usage`, `cost_usd` and `status`
    exist on assistant rows only; user rows carry `content` alone.
    """

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_session_created", "session_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    seq: Mapped[int] = mapped_column(
        BigInteger, CHAT_MESSAGE_SEQ, nullable=False, unique=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    activity: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    structured: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost_usd: Mapped[str | None] = mapped_column(Numeric(12, 8), nullable=True)
    execution_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("executions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
