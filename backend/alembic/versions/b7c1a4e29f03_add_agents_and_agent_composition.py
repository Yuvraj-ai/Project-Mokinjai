"""add agents and agent composition

Revision ID: b7c1a4e29f03
Revises: dc9de95d49bd
Create Date: 2026-10-19 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7c1a4e29f03'
down_revision: Union[str, None] = 'dc9de95d49bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "llm_profiles",
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
    )

    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("llm_profile_id", sa.String(length=36), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("source_prompt_id", sa.String(length=36), nullable=True),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("structured_output_id", sa.String(length=36), nullable=True),
        sa.Column("web_search", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["llm_profile_id"], ["llm_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_prompt_id"], ["prompt_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["structured_output_id"], ["structured_outputs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agents_workspace_id", "agents", ["workspace_id"])
    op.create_index("ix_agents_llm_profile_id", "agents", ["llm_profile_id"])
    op.create_index("ix_agents_structured_output_id", "agents", ["structured_output_id"])
    op.execute(
        "CREATE UNIQUE INDEX uq_agents_workspace_name_lower "
        "ON agents (workspace_id, lower(name))"
    )

    op.create_table(
        "agent_tools",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("tool_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id", "tool_id"),
    )
    op.create_index("ix_agent_tools_tool_id", "agent_tools", ["tool_id"])

    op.create_table(
        "agent_skills",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("skill_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id", "skill_id"),
    )
    op.create_index("ix_agent_skills_skill_id", "agent_skills", ["skill_id"])

    op.create_table(
        "agent_knowledge_bases",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id", "knowledge_base_id"),
    )
    op.create_index(
        "ix_agent_knowledge_bases_knowledge_base_id",
        "agent_knowledge_bases",
        ["knowledge_base_id"],
    )

    op.create_table(
        "agent_connectors",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("connector_instance_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["connector_instance_id"], ["connector_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id", "connector_instance_id"),
    )
    op.create_index(
        "ix_agent_connectors_connector_instance_id",
        "agent_connectors",
        ["connector_instance_id"],
    )

    op.create_table(
        "agent_subagents",
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("subagent_id", sa.String(length=36), nullable=False),
        sa.CheckConstraint("agent_id <> subagent_id", name="ck_agent_subagents_not_self"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subagent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id", "subagent_id"),
    )
    op.create_index("ix_agent_subagents_subagent_id", "agent_subagents", ["subagent_id"])

    op.create_table(
        "resource_usage",
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", sa.String(length=20), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id", "resource_type", "resource_id"),
    )
    op.create_index(
        "ix_resource_usage_workspace_type_last_used",
        "resource_usage",
        ["workspace_id", "resource_type", "last_used_at"],
    )

    op.create_table(
        "search_credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("encrypted_api_key", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "provider", name="uq_search_credentials_workspace_provider"
        ),
    )
    op.create_index("ix_search_credentials_workspace_id", "search_credentials", ["workspace_id"])

    op.add_column("executions", sa.Column("agent_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_executions_agent_id_agents", "executions", "agents", ["agent_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_executions_agent_id", "executions", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_executions_agent_id", table_name="executions")
    op.drop_constraint("fk_executions_agent_id_agents", "executions", type_="foreignkey")
    op.drop_column("executions", "agent_id")

    op.drop_index("ix_search_credentials_workspace_id", table_name="search_credentials")
    op.drop_table("search_credentials")

    op.drop_index("ix_resource_usage_workspace_type_last_used", table_name="resource_usage")
    op.drop_table("resource_usage")

    op.drop_index("ix_agent_subagents_subagent_id", table_name="agent_subagents")
    op.drop_table("agent_subagents")

    op.drop_index("ix_agent_connectors_connector_instance_id", table_name="agent_connectors")
    op.drop_table("agent_connectors")

    op.drop_index("ix_agent_knowledge_bases_knowledge_base_id", table_name="agent_knowledge_bases")
    op.drop_table("agent_knowledge_bases")

    op.drop_index("ix_agent_skills_skill_id", table_name="agent_skills")
    op.drop_table("agent_skills")

    op.drop_index("ix_agent_tools_tool_id", table_name="agent_tools")
    op.drop_table("agent_tools")

    op.execute("DROP INDEX IF EXISTS uq_agents_workspace_name_lower")
    op.drop_index("ix_agents_structured_output_id", table_name="agents")
    op.drop_index("ix_agents_llm_profile_id", table_name="agents")
    op.drop_index("ix_agents_workspace_id", table_name="agents")
    op.drop_table("agents")

    op.drop_column("llm_profiles", "max_output_tokens")
