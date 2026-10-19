import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ResourceUsage(Base):
    """How recently a pickable resource was used, per workspace.

    Polymorphic on purpose: `resource_id` has no foreign key because the table
    covers several resource types. Rows disappear with their workspace, and
    every query filters by `resource_type`.
    """

    __tablename__ = "resource_usage"
    __table_args__ = (
        Index("ix_resource_usage_workspace_type_last_used", "workspace_id", "resource_type", "last_used_at"),
    )

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    resource_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


async def bump_usage(
    session: AsyncSession, workspace_id: str, resource_type: str, resource_id: str
) -> None:
    """Record one use of a resource. The caller owns the transaction."""
    statement = (
        insert(ResourceUsage)
        .values(
            workspace_id=workspace_id,
            resource_type=resource_type,
            resource_id=resource_id,
            use_count=1,
        )
        .on_conflict_do_update(
            index_elements=["workspace_id", "resource_type", "resource_id"],
            set_={
                "last_used_at": func.now(),
                "use_count": ResourceUsage.use_count + 1,
            },
        )
    )
    await session.execute(statement)
