import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Agent(Base):
    """A saved agent configuration.

    The row stores references and scalars only. Tools are never stored as a
    resolved set: they are derived from the selected skills and tools at run
    start (ADR-016). `source_prompt_id` records where the system prompt was
    copied from; it is provenance, not a live reference (prompts are snapshots).
    """

    __tablename__ = "agents"
    __table_args__ = (
        Index("uq_agents_workspace_name_lower", "workspace_id", text("lower(name)"), unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_profile_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("llm_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    source_prompt_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("prompt_templates.id", ondelete="SET NULL"), nullable=True
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    structured_output_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("structured_outputs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    web_search: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace = relationship("Workspace", back_populates="agents")
    llm_profile = relationship("LlmProfile")
    structured_output = relationship("StructuredOutput")
    source_prompt = relationship("PromptTemplate")
    skills = relationship("AgentSkill", back_populates="agent", cascade="all, delete-orphan")
    documents = relationship(
        "AgentDocument", back_populates="agent", cascade="all, delete-orphan"
    )
    connectors = relationship("AgentConnector", back_populates="agent", cascade="all, delete-orphan")
    tools = relationship("AgentTool", back_populates="agent", cascade="all, delete-orphan")
    data_sources = relationship(
        "AgentDataSource", back_populates="agent", cascade="all, delete-orphan"
    )
    subagents = relationship(
        "AgentSubagent",
        back_populates="agent",
        cascade="all, delete-orphan",
        foreign_keys="AgentSubagent.agent_id",
    )


class AgentSkill(Base):
    __tablename__ = "agent_skills"
    __table_args__ = (Index("ix_agent_skills_skill_id", "skill_id"),)

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )

    agent = relationship("Agent", back_populates="skills")


class AgentTool(Base):
    """Direct tool selections. Skill-required tools are derived, never stored."""

    __tablename__ = "agent_tools"
    __table_args__ = (Index("ix_agent_tools_tool_id", "tool_id"),)

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    tool_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tools.id", ondelete="CASCADE"), primary_key=True
    )

    agent = relationship("Agent", back_populates="tools")


class AgentDocument(Base):
    """One file attached to one agent.

    A folder attachment is flattened to these rows at save time (spec, Option A), so the
    snapshot is the storage itself. `source_folder_id` exists only so the picker can group
    the files by the rule that attached them; it is not a live reference.
    """

    __tablename__ = "agent_documents"
    __table_args__ = (Index("ix_agent_documents_document_id", "document_id"),)

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="RESTRICT"), primary_key=True
    )
    source_folder_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("file_folders.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    agent = relationship("Agent", back_populates="documents")


class AgentConnector(Base):
    __tablename__ = "agent_connectors"
    __table_args__ = (Index("ix_agent_connectors_connector_instance_id", "connector_instance_id"),)

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    connector_instance_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("connector_instances.id", ondelete="CASCADE"), primary_key=True
    )

    agent = relationship("Agent", back_populates="connectors")


class AgentSubagent(Base):
    """One edge of the subagent graph. Cycles are rejected in the service layer.

    The database refuses only the one-edge case, an agent naming itself; longer
    cycles need the full graph and are validated before save.
    """

    __tablename__ = "agent_subagents"
    __table_args__ = (
        CheckConstraint("agent_id <> subagent_id", name="ck_agent_subagents_not_self"),
        Index("ix_agent_subagents_subagent_id", "subagent_id"),
    )

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    subagent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )

    agent = relationship("Agent", back_populates="subagents", foreign_keys=[agent_id])
    subagent = relationship("Agent", foreign_keys=[subagent_id])


class AgentDataSource(Base):
    """One external database connection attached to one agent (D4).

    `tables` is the allowlist snapshot: the exact qualified names the agent may
    query. Tables created in the database later are not queryable until the
    user re-saves. The connection FK is RESTRICT — an attached connection can
    only be deleted after the agent detaches it.
    """

    __tablename__ = "agent_data_sources"
    __table_args__ = (Index("ix_agent_data_sources_connection_id", "connection_id"),)

    agent_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("external_database_connections.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    tables: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    agent = relationship("Agent", back_populates="data_sources")
