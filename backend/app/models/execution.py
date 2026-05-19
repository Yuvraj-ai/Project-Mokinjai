import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, Numeric, func, JSON
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workflow_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workflows.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workflow_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # pending, running, completed, failed, cancelled
    trigger_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # manual, api, scheduled, webhook
    input_data: Mapped[dict | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    output_data: Mapped[dict | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    mongo_trace_id: Mapped[str | None] = mapped_column(String(24), nullable=True) # MongoDB ObjectId reference
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(MutableDict.as_mutable(JSON), nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workflow = relationship("Workflow", back_populates="executions")
