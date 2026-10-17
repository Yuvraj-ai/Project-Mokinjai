"""add external database connections

Revision ID: a525a8b786ec
Revises: 8e5be3569090
Create Date: 2026-10-16 22:10:10.311286

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a525a8b786ec"
down_revision: Union[str, None] = "8e5be3569090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_database_connections",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("encrypted_uri", sa.LargeBinary(), nullable=False),
        sa.Column("database_name", sa.String(length=255), nullable=True),
        sa.Column("collection_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_external_database_connections_workspace_id",
        "external_database_connections",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_database_connections_workspace_id",
        table_name="external_database_connections",
    )
    op.drop_table("external_database_connections")
