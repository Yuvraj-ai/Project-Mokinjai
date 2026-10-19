"""Load and validate everything an agent configuration points at.

The router owns HTTP; this module owns the rules. It is also what the runtime
uses to turn a saved agent into its resolved dependencies, so a saved agent is
resolved exactly the way it was validated.

Errors are collected rather than raised one at a time: a form that has three
problems should say three things.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import (
    Agent,
    AgentConnector,
    AgentKnowledgeBase,
    AgentSkill,
    AgentSubagent,
    AgentTool,
)
from app.models.connector import ConnectorInstance
from app.models.knowledge import KnowledgeBase
from app.models.llm_profile import LlmProfile
from app.models.prompt import PromptTemplate
from app.models.search_credential import SearchCredential
from app.models.skill import Skill
from app.models.structured_output import StructuredOutput
from app.models.tool import Tool
from app.services.agent_capabilities import Capabilities, capabilities_for
from app.services.agent_dependencies import (
    ResolvedSkills,
    SubagentGraphError,
    effective_tool_names,
    resolve_skills,
    validate_subagent_selection,
)
from app.services.agent_validation import (
    AgentValidationError,
    FieldError,
    normalise_params,
    normalise_web_search,
)
from app.services.skill import SkillDefinition, SkillError
from app.services.structured_output import (
    Definition,
    StructuredOutputError,
    compile_schema,
)


class CompositionError(Exception):
    def __init__(self, errors: list[FieldError]):
        self.errors = errors
        super().__init__("; ".join(f"{error.field}: {error.message}" for error in errors))


@dataclass(frozen=True)
class AgentInput:
    name: str
    description: str | None
    llm_profile_id: str
    system_prompt: str
    source_prompt_id: str | None
    params: dict[str, Any]
    structured_output_id: str | None
    web_search: dict[str, Any] | None
    skill_ids: list[str] = field(default_factory=list)
    tool_ids: list[str] = field(default_factory=list)
    knowledge_base_ids: list[str] = field(default_factory=list)
    connector_ids: list[str] = field(default_factory=list)
    subagent_ids: list[str] = field(default_factory=list)


@dataclass
class ValidatedAgent:
    profile: LlmProfile
    capabilities: Capabilities
    params: dict[str, Any]
    web_search: dict[str, Any] | None
    structured_output: StructuredOutput | None
    structured_schema: dict[str, Any] | None
    selected_skills: list[Skill]
    resolved_skills: ResolvedSkills
    direct_tools: list[Tool]
    workspace_tools: list[Tool]
    effective_tools: tuple[str, ...]
    knowledge_bases: list[KnowledgeBase]
    connectors: list[ConnectorInstance]
    subagents: list[Agent]
    source_prompt: PromptTemplate | None


def _skill_definition(row: Skill) -> SkillDefinition:
    return SkillDefinition(name=row.name, description=row.description, content=row.content)


def _definition(row: StructuredOutput) -> Definition:
    return Definition(name=row.name, description=row.description, fields=list(row.fields or []))


async def validate_agent(
    db: AsyncSession,
    workspace_id: str,
    data: AgentInput,
    *,
    agent_id: str | None,
) -> ValidatedAgent:
    errors: list[FieldError] = []

    profile = (
        await db.execute(
            select(LlmProfile).where(
                LlmProfile.id == data.llm_profile_id,
                LlmProfile.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    capabilities: Capabilities | None = None
    if profile is None:
        errors.append(FieldError("llm_profile_id", "does not exist in this workspace"))
    elif profile.status != "verified":
        errors.append(
            FieldError(
                "llm_profile_id",
                f"must be verified (last test status: {profile.status})",
            )
        )
    else:
        capabilities = capabilities_for(
            profile.provider, profile.model_id, max_output_tokens_override=profile.max_output_tokens
        )

    params: dict[str, Any] = {}
    web_search: dict[str, Any] | None = None
    if capabilities is not None:
        try:
            params = normalise_params(data.params, capabilities)
        except AgentValidationError as exc:
            errors.extend(exc.errors)

        try:
            credentials = set(
                (
                    await db.execute(
                        select(SearchCredential.provider).where(
                            SearchCredential.workspace_id == workspace_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            web_search = normalise_web_search(
                data.web_search,
                capabilities,
                has_credential=lambda provider: provider in credentials,
            )
        except AgentValidationError as exc:
            errors.extend(exc.errors)

    structured_output, structured_schema = await _load_structured_output(
        db, workspace_id, data.structured_output_id, errors
    )
    selected_skills, resolved = await _load_skills(db, workspace_id, data.skill_ids, errors)
    direct_tools, workspace_tools, effective_tools = await _load_tools(
        db, workspace_id, data.tool_ids, resolved, errors
    )
    knowledge_bases = await _load_all(db, KnowledgeBase, workspace_id, data.knowledge_base_ids, "knowledge_base_ids", errors)
    connectors = await _load_all(db, ConnectorInstance, workspace_id, data.connector_ids, "connector_ids", errors)
    subagents = await _load_subagents(db, workspace_id, data.subagent_ids, agent_id, errors)
    source_prompt = await _load_source_prompt(db, workspace_id, data.source_prompt_id, errors)

    disabled = [row.name for row in connectors if row.status != "enabled"]
    if disabled:
        errors.append(
            FieldError("connector_ids", "must be enabled: " + ", ".join(sorted(disabled)))
        )

    if errors:
        raise CompositionError(errors)

    return ValidatedAgent(
        profile=profile,
        capabilities=capabilities,
        params=params,
        web_search=web_search,
        structured_output=structured_output,
        structured_schema=structured_schema,
        selected_skills=selected_skills,
        resolved_skills=resolved,
        direct_tools=direct_tools,
        workspace_tools=workspace_tools,
        effective_tools=effective_tools,
        knowledge_bases=knowledge_bases,
        connectors=connectors,
        subagents=subagents,
        source_prompt=source_prompt,
    )


async def _load_structured_output(
    db: AsyncSession,
    workspace_id: str,
    output_id: str | None,
    errors: list[FieldError],
) -> tuple[StructuredOutput | None, dict[str, Any] | None]:
    if not output_id:
        return None, None

    rows = list(
        (
            await db.execute(
                select(StructuredOutput).where(StructuredOutput.workspace_id == workspace_id)
            )
        )
        .scalars()
        .all()
    )
    selected = next((row for row in rows if row.id == output_id), None)
    if selected is None:
        errors.append(FieldError("structured_output_id", "does not exist in this workspace"))
        return None, None

    try:
        schema = compile_schema(_definition(selected), {row.name: _definition(row) for row in rows})
    except StructuredOutputError as exc:
        errors.append(FieldError("structured_output_id", str(exc)))
        return selected, None
    return selected, schema


async def _load_skills(
    db: AsyncSession,
    workspace_id: str,
    skill_ids: list[str],
    errors: list[FieldError],
) -> tuple[list[Skill], ResolvedSkills]:
    rows = list(
        (await db.execute(select(Skill).where(Skill.workspace_id == workspace_id))).scalars().all()
    )
    by_id = {row.id: row for row in rows}
    missing = [skill_id for skill_id in skill_ids if skill_id not in by_id]
    if missing:
        errors.append(FieldError("skill_ids", "do not exist in this workspace: " + ", ".join(missing)))

    selected = [by_id[skill_id] for skill_id in skill_ids if skill_id in by_id]
    empty = ResolvedSkills(menu=(), skill_closure=(), contents={}, tool_names=())
    try:
        resolved = resolve_skills(
            [row.name for row in selected], {row.name: _skill_definition(row) for row in rows}
        )
    except SkillError as exc:
        errors.append(FieldError("skill_ids", str(exc)))
        return selected, empty
    return selected, resolved


async def _load_tools(
    db: AsyncSession,
    workspace_id: str,
    tool_ids: list[str],
    resolved: ResolvedSkills,
    errors: list[FieldError],
) -> tuple[list[Tool], list[Tool], tuple[str, ...]]:
    from app.tools import list_builtin_tools

    rows = list(
        (await db.execute(select(Tool).where(Tool.workspace_id == workspace_id))).scalars().all()
    )
    by_id = {row.id: row for row in rows}
    missing = [tool_id for tool_id in tool_ids if tool_id not in by_id]
    if missing:
        errors.append(FieldError("tool_ids", "do not exist in this workspace: " + ", ".join(missing)))

    direct = [by_id[tool_id] for tool_id in tool_ids if tool_id in by_id]
    effective = effective_tool_names(resolved.tool_names, [row.name for row in direct])

    known = {row.name.lower() for row in rows}
    known.update(entry.key.lower() for entry in list_builtin_tools())
    unknown = [name for name in effective if name.lower() not in known]
    if unknown:
        errors.append(
            FieldError(
                "skill_ids",
                "reference tools that no longer exist: " + ", ".join(sorted(unknown)),
            )
        )
    return direct, rows, effective


async def _load_all(
    db: AsyncSession,
    model: type,
    workspace_id: str,
    ids: list[str],
    field: str,
    errors: list[FieldError],
) -> list:
    if not ids:
        return []
    rows = list(
        (await db.execute(select(model).where(model.workspace_id == workspace_id))).scalars().all()
    )
    by_id = {row.id: row for row in rows}
    missing = [item_id for item_id in ids if item_id not in by_id]
    if missing:
        errors.append(FieldError(field, "do not exist in this workspace: " + ", ".join(missing)))
    return [by_id[item_id] for item_id in ids if item_id in by_id]


async def _load_subagents(
    db: AsyncSession,
    workspace_id: str,
    subagent_ids: list[str],
    agent_id: str | None,
    errors: list[FieldError],
) -> list[Agent]:
    rows = list(
        (await db.execute(select(Agent).where(Agent.workspace_id == workspace_id))).scalars().all()
    )
    by_id = {row.id: row for row in rows}
    missing = [subagent_id for subagent_id in subagent_ids if subagent_id not in by_id]
    if missing:
        errors.append(
            FieldError("subagent_ids", "do not exist in this workspace: " + ", ".join(missing))
        )
        return []

    edges: dict[str, list[str]] = {}
    link_rows = (
        await db.execute(
            select(AgentSubagent)
            .join(Agent, Agent.id == AgentSubagent.agent_id)
            .where(Agent.workspace_id == workspace_id)
        )
    ).scalars()
    for link in link_rows:
        edges.setdefault(link.agent_id, []).append(link.subagent_id)

    try:
        validate_subagent_selection(
            agent_id or "",
            subagent_ids,
            edges,
            known_ids=set(by_id),
        )
    except SubagentGraphError as exc:
        errors.append(FieldError("subagent_ids", str(exc)))
        return []

    return [by_id[subagent_id] for subagent_id in subagent_ids]


async def _load_source_prompt(
    db: AsyncSession,
    workspace_id: str,
    prompt_id: str | None,
    errors: list[FieldError],
) -> PromptTemplate | None:
    if not prompt_id:
        return None
    row = (
        await db.execute(
            select(PromptTemplate).where(
                PromptTemplate.id == prompt_id,
                PromptTemplate.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        errors.append(FieldError("source_prompt_id", "does not exist in this workspace"))
    return row


async def join_ids(db: AsyncSession, agent_id: str) -> dict[str, list[str]]:
    """The five composition join tables, as ids."""
    skills = (
        await db.execute(select(AgentSkill.skill_id).where(AgentSkill.agent_id == agent_id))
    ).scalars().all()
    tools = (
        await db.execute(select(AgentTool.tool_id).where(AgentTool.agent_id == agent_id))
    ).scalars().all()
    knowledge_bases = (
        await db.execute(
            select(AgentKnowledgeBase.knowledge_base_id).where(
                AgentKnowledgeBase.agent_id == agent_id
            )
        )
    ).scalars().all()
    connectors = (
        await db.execute(
            select(AgentConnector.connector_instance_id).where(
                AgentConnector.agent_id == agent_id
            )
        )
    ).scalars().all()
    subagents = (
        await db.execute(
            select(AgentSubagent.subagent_id).where(AgentSubagent.agent_id == agent_id)
        )
    ).scalars().all()
    return {
        "skill_ids": list(skills),
        "tool_ids": list(tools),
        "knowledge_base_ids": list(knowledge_bases),
        "connector_ids": list(connectors),
        "subagent_ids": list(subagents),
    }


async def saved_input(db: AsyncSession, agent: Agent) -> AgentInput:
    """A saved agent as the same input the form sends, for revalidation at run time."""
    ids = await join_ids(db, agent.id)
    return AgentInput(
        name=agent.name,
        description=agent.description,
        llm_profile_id=agent.llm_profile_id or "",
        system_prompt=agent.system_prompt,
        source_prompt_id=agent.source_prompt_id,
        params=dict(agent.params or {}),
        structured_output_id=agent.structured_output_id,
        web_search=agent.web_search,
        **ids,
    )


async def assert_name_is_free(
    db: AsyncSession, workspace_id: str, name: str, *, exclude_id: str | None
) -> None:
    query = select(Agent).where(
        Agent.workspace_id == workspace_id,
        func.lower(Agent.name) == name.strip().lower(),
    )
    if exclude_id:
        query = query.where(Agent.id != exclude_id)
    existing = (await db.execute(query)).scalars().first()
    if existing is not None:
        from app.utils.errors import ConflictException

        raise ConflictException(f'An agent named "{existing.name}" already exists.')
