"""add llm profiles

Revision ID: c4e1a9b2d7f0
Revises: 8b8151205831
Create Date: 2026-10-13 02:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4e1a9b2d7f0"
down_revision: Union[str, None] = "8b8151205831"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("encrypted_api_key", sa.LargeBinary(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=False),
        sa.Column("compaction_at_tokens", sa.Integer(), nullable=False),
        sa.Column("input_price_per_million", sa.Float(), nullable=False),
        sa.Column("output_price_per_million", sa.Float(), nullable=False),
        sa.Column("cache_price_per_million", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_profiles_workspace_id", "llm_profiles", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_profiles_workspace_id", table_name="llm_profiles")
    op.drop_table("llm_profiles")
