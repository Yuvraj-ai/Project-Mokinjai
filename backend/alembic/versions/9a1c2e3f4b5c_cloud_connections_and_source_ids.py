"""cloud connections and document source ids

Both additions serve on-demand import: a per-user encrypted refresh token, and
provenance columns on `documents` whose unique constraint makes a re-import return the
existing row instead of creating a duplicate. The columns are nullable and Postgres
treats NULLs as distinct, so ordinary uploads are unaffected.

Revision ID: 9a1c2e3f4b5c
Revises: 151dbc8cdfca
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9a1c2e3f4b5c"
down_revision: Union[str, None] = "151dbc8cdfca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cloud_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("account_label", sa.String(255), nullable=True),
        sa.Column("refresh_token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "provider", name="uq_cloud_connections_user_provider"),
    )
    op.create_index(
        "ix_cloud_connections_user_id", "cloud_connections", ["user_id"]
    )

    op.add_column("documents", sa.Column("source_provider", sa.String(32), nullable=True))
    op.add_column("documents", sa.Column("source_id", sa.String(255), nullable=True))
    op.create_unique_constraint(
        "uq_documents_workspace_source",
        "documents",
        ["workspace_id", "source_provider", "source_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_documents_workspace_source", "documents", type_="unique")
    op.drop_column("documents", "source_id")
    op.drop_column("documents", "source_provider")
    op.drop_index("ix_cloud_connections_user_id", table_name="cloud_connections")
    op.drop_table("cloud_connections")
