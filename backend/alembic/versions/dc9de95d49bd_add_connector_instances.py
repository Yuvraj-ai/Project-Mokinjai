"""add connector instances

Revision ID: dc9de95d49bd
Revises: a525a8b786ec
Create Date: 2026-10-17 01:45:46.029744

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'dc9de95d49bd'
down_revision: Union[str, None] = 'a525a8b786ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connector_instances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("connector_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "auth_scope",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'workspace'"),
        ),
        sa.Column("auth_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tool_names", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_connector_instances_workspace_id", "connector_instances", ["workspace_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_connector_instances_workspace_id", table_name="connector_instances")
    op.drop_table("connector_instances")
