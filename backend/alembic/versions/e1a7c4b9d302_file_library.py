"""turn knowledge bases into the workspace file library

Revision ID: e1a7c4b9d302
Revises: b7c1a4e29f03
Create Date: 2026-10-23 13:20:00.000000

The development database carries no data worth preserving, so this is the clean
transform the design names (docs/superpowers/specs/2026-10-23-file-library-design.md):
one folder table, files scoped to a workspace, and one attachment table.

`knowledge_base_id` is deliberately left nullable after `downgrade`. Root files have no
folder, and deleting them to satisfy the old NOT NULL would destroy real bytes. The old
code assumed a folder everywhere, so a downgraded database with root files is not a
supported state — it is merely a state that loses nothing.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e1a7c4b9d302"
down_revision: Union[str, None] = "b7c1a4e29f03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("knowledge_bases", "file_folders")
    op.drop_column("file_folders", "description")
    op.drop_column("file_folders", "type")
    op.drop_column("file_folders", "config")

    # A root file has no folder to derive its workspace from, so the workspace is on the
    # row. Every pre-existing file has a folder, which makes the backfill total.
    op.add_column("documents", sa.Column("workspace_id", sa.String(length=36), nullable=True))
    op.execute(
        """
        UPDATE documents AS d
        SET workspace_id = f.workspace_id
        FROM file_folders AS f
        WHERE d.knowledge_base_id = f.id
        """
    )
    op.alter_column("documents", "workspace_id", nullable=False)
    op.create_foreign_key(
        "fk_documents_workspace_id",
        "documents",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_documents_workspace_id", "documents", ["workspace_id"])

    op.drop_index("ix_documents_knowledge_base_id", table_name="documents")
    op.drop_constraint("documents_knowledge_base_id_fkey", "documents", type_="foreignkey")
    op.alter_column("documents", "knowledge_base_id", new_column_name="folder_id", nullable=True)
    op.create_index("ix_documents_folder_id", "documents", ["folder_id"])
    op.create_foreign_key(
        "fk_documents_folder_id",
        "documents",
        "file_folders",
        ["folder_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_table("agent_knowledge_bases")
    op.create_table(
        "agent_documents",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("source_folder_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_folder_id"], ["file_folders.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("agent_id", "document_id"),
    )
    op.create_index("ix_agent_documents_document_id", "agent_documents", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_documents_document_id", table_name="agent_documents")
    op.drop_table("agent_documents")

    op.create_table(
        "agent_knowledge_bases",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["file_folders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id", "knowledge_base_id"),
    )
    op.create_index(
        "ix_agent_knowledge_bases_knowledge_base_id",
        "agent_knowledge_bases",
        ["knowledge_base_id"],
    )

    op.drop_constraint("fk_documents_folder_id", "documents", type_="foreignkey")
    op.drop_index("ix_documents_folder_id", table_name="documents")
    op.alter_column("documents", "folder_id", new_column_name="knowledge_base_id", nullable=True)
    op.create_index("ix_documents_knowledge_base_id", "documents", ["knowledge_base_id"])
    op.create_foreign_key(
        "documents_knowledge_base_id_fkey",
        "documents",
        "file_folders",
        ["knowledge_base_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_index("ix_documents_workspace_id", table_name="documents")
    op.drop_constraint("fk_documents_workspace_id", "documents", type_="foreignkey")
    op.drop_column("documents", "workspace_id")

    op.add_column("file_folders", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "file_folders",
        sa.Column("type", sa.String(length=50), nullable=False, server_default="document"),
    )
    op.add_column(
        "file_folders",
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.rename_table("file_folders", "knowledge_bases")
