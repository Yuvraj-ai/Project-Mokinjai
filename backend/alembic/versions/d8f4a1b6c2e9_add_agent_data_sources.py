"""add agent_data_sources

Revision ID: d8f4a1b6c2e9
Revises: e1a7c4b9d302
Create Date: 2026-11-01

The per-agent allowlist for external data sources (D4). Composite PK like the
other agent join tables; the connection side is RESTRICT so an attached
connection can only be deleted after the agent detaches it.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "d8f4a1b6c2e9"
down_revision: Union[str, None] = "e1a7c4b9d302"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_data_sources",
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("connection_id", sa.String(36), nullable=False),
        sa.Column("tables", JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("agent_id", "connection_id"),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"], ["external_database_connections.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_agent_data_sources_connection_id",
        "agent_data_sources",
        ["connection_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_data_sources_connection_id", table_name="agent_data_sources")
    op.drop_table("agent_data_sources")
