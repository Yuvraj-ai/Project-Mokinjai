import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.models.agent import (
    Agent,
    AgentConnector,
    AgentKnowledgeBase,
    AgentSkill,
    AgentSubagent,
    AgentTool,
)
from app.models.connector import ConnectorInstance
from app.models.execution import Execution
from app.models.knowledge import KnowledgeBase
from app.models.llm_profile import LlmProfile
from app.models.resource_usage import ResourceUsage, bump_usage
from app.models.search_credential import SearchCredential
from app.models.skill import Skill
from app.models.structured_output import StructuredOutput
from app.models.tool import Tool
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.agent import (
    AgentCapabilitiesResponse,
    AgentChatRequest,
    AgentListItem,
    AgentListResponse,
    AgentOption,
    AgentOptionsResponse,
    AgentResponse,
    AgentWriteRequest,
    ResolvedDependencies,
    ResolvedSkill,
    ResolvedTool,
)
from app.services.agent_capabilities import capabilities_for
from app.services.agent_composition import (
    AgentInput,
    CompositionError,
    assert_name_is_free,
    join_ids,
    validate_agent,
)
from app.services.agent_dependencies import effective_tool_names, resolve_skills
from app.services.agent_validation import AgentValidationError, normalise_params
from app.services.agent_runtime import stream_chat
from app.services.skill import SkillDefinition, SkillError, extract_references
from app.services.structured_output import (
    Definition,
    StructuredOutputError,
    compile_schema,
)
from app.services.tool_schema import extract_schema, extraction_error
from app.utils.errors import ConflictException, NotFoundException

router = APIRouter()


def _sse(events):
    async def generate():
        async for event in events:
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

    return generate()


def _input(request: AgentWriteRequest) -> AgentInput:
    return AgentInput(
        name=request.name,
        description=request.description,
        llm_profile_id=request.llm_profile_id,
        system_prompt=request.system_prompt,
        source_prompt_id=request.source_prompt_id,
        params=request.params,
        structured_output_id=request.structured_output_id,
        web_search=request.web_search,
        skill_ids=request.skill_ids,
        tool_ids=request.tool_ids,
        knowledge_base_ids=request.knowledge_base_ids,
        connector_ids=request.connector_ids,
        subagent_ids=request.subagent_ids,
    )


def _raise_composition(exc: CompositionError) -> None:
    raise HTTPException(
        status_code=422,
        detail=[
            {"loc": ["body", error.field], "msg": error.message, "type": "value_error"}
            for error in exc.errors
        ],
    )


async def _load_agent(db: AsyncSession, workspace_id: str, agent_id: str) -> Agent:
    row = (
        await db.execute(
            select(Agent).where(Agent.id == agent_id, Agent.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundException("Agent")
    return row


async def _join_ids(db: AsyncSession, agent_id: str) -> dict[str, list[str]]:
    return await join_ids(db, agent_id)


def _add_joins(db: AsyncSession, agent_id: str, ids: dict[str, list[str]]) -> None:
    db.add_all([AgentSkill(agent_id=agent_id, skill_id=value) for value in ids["skill_ids"]])
    db.add_all([AgentTool(agent_id=agent_id, tool_id=value) for value in ids["tool_ids"]])
    db.add_all(
        [
            AgentKnowledgeBase(agent_id=agent_id, knowledge_base_id=value)
            for value in ids["knowledge_base_ids"]
        ]
    )
    db.add_all(
        [
            AgentConnector(agent_id=agent_id, connector_instance_id=value)
            for value in ids["connector_ids"]
        ]
    )
    db.add_all(
        [AgentSubagent(agent_id=agent_id, subagent_id=value) for value in ids["subagent_ids"]]
    )


async def _replace_joins(db: AsyncSession, agent_id: str, ids: dict[str, list[str]]) -> None:
    for model in (AgentSkill, AgentTool, AgentKnowledgeBase, AgentConnector, AgentSubagent):
        await db.execute(delete(model).where(model.agent_id == agent_id))
    _add_joins(db, agent_id, ids)


def _ids_from_validated(validated) -> dict[str, list[str]]:
    return {
        "skill_ids": [row.id for row in validated.selected_skills],
        "tool_ids": [row.id for row in validated.direct_tools],
        "knowledge_base_ids": [row.id for row in validated.knowledge_bases],
        "connector_ids": [row.id for row in validated.connectors],
        "subagent_ids": [row.id for row in validated.subagents],
    }


def _capabilities_response(profile: LlmProfile | None) -> AgentCapabilitiesResponse | None:
    if profile is None:
        return None
    try:
        capabilities = capabilities_for(
            profile.provider,
            profile.model_id,
            max_output_tokens_override=profile.max_output_tokens,
        )
    except ValueError:
        return None
    return AgentCapabilitiesResponse(**capabilities.as_dict())


async def _to_response(
    db: AsyncSession, agent: Agent, *, join_ids: dict[str, list[str]] | None = None
) -> AgentResponse:
    ids = join_ids or await _join_ids(db, agent.id)
    profile = (
        await db.get(LlmProfile, agent.llm_profile_id) if agent.llm_profile_id else None
    )
    capabilities = _capabilities_response(profile)

    all_skills = list(
        (
            await db.execute(select(Skill).where(Skill.workspace_id == agent.workspace_id))
        )
        .scalars()
        .all()
    )
    selected_skills = [row for row in all_skills if row.id in ids["skill_ids"]]
    selected_names = {row.name for row in selected_skills}

    issues: list[str] = []
    if profile is None:
        issues.append("Select a verified LLM profile.")
    elif profile.status != "verified":
        issues.append(f"The selected LLM profile is {profile.status}.")

    resolved_skills = None
    try:
        resolved_skills = resolve_skills(
            [row.name for row in selected_skills],
            {
                row.name: SkillDefinition(
                    name=row.name, description=row.description, content=row.content
                )
                for row in all_skills
            },
        )
    except SkillError as exc:
        issues.append(str(exc))

    if capabilities is not None:
        try:
            normalise_params(agent.params, capabilities)
        except AgentValidationError as exc:
            issues.extend(f"{error.field}: {error.message}" for error in exc.errors)

    if agent.structured_output_id:
        output = await db.get(StructuredOutput, agent.structured_output_id)
        if output is None:
            issues.append("The selected structured output was deleted.")
        else:
            outputs = list(
                (
                    await db.execute(
                        select(StructuredOutput).where(
                            StructuredOutput.workspace_id == agent.workspace_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            try:
                compile_schema(
                    Definition(
                        name=output.name,
                        description=output.description,
                        fields=list(output.fields or []),
                    ),
                    {
                        row.name: Definition(
                            name=row.name,
                            description=row.description,
                            fields=list(row.fields or []),
                        )
                        for row in outputs
                    },
                )
            except StructuredOutputError as exc:
                issues.append(f"structured output: {exc}")

    if agent.web_search and agent.web_search.get("method") in ("tavily", "exa"):
        method = agent.web_search["method"]
        credential = (
            await db.execute(
                select(SearchCredential).where(
                    SearchCredential.workspace_id == agent.workspace_id,
                    SearchCredential.provider == method,
                )
            )
        ).scalar_one_or_none()
        if credential is None:
            issues.append(f"Add an API key for {method}.")

    connectors = list(
        (
            await db.execute(
                select(ConnectorInstance).where(
                    ConnectorInstance.id.in_(ids["connector_ids"]),
                    ConnectorInstance.workspace_id == agent.workspace_id,
                )
            )
        )
        .scalars()
        .all()
    ) if ids["connector_ids"] else []
    for connector in connectors:
        if connector.status != "enabled":
            issues.append(f"Connector {connector.name} is {connector.status}.")

    all_tools = list(
        (await db.execute(select(Tool).where(Tool.workspace_id == agent.workspace_id)))
        .scalars()
        .all()
    )
    direct_tools = [row for row in all_tools if row.id in ids["tool_ids"]]
    workspace_tools = {row.name.lower(): row for row in all_tools}
    required = {name.lower() for name in (resolved_skills.tool_names if resolved_skills else ())}
    tool_names = effective_tool_names(
        resolved_skills.tool_names if resolved_skills else (),
        [row.name for row in direct_tools],
    )
    for name in tool_names:
        row = workspace_tools.get(name.lower())
        if row is None:
            continue
        extracted = extract_schema(row.code)
        if extracted.schema is None:
            issues.append(extraction_error(row.name, extracted))

    resolved = ResolvedDependencies(
        skills=[
            ResolvedSkill(
                id=next(
                    (
                        row.id
                        for row in all_skills
                        if row.name.lower() == name.lower()
                    ),
                    "",
                ),
                name=name,
                root=name in selected_names,
            )
            for name in (resolved_skills.skill_closure if resolved_skills else ())
        ],
        tools=[
            ResolvedTool(
                name=workspace_tools[name.lower()].name if name.lower() in workspace_tools else name,
                source="workspace" if name.lower() in workspace_tools else "builtin",
                locked=name.lower() in required,
                tool_id=workspace_tools[name.lower()].id if name.lower() in workspace_tools else None,
            )
            for name in tool_names
        ],
    )

    return AgentResponse(
        id=agent.id,
        workspace_id=agent.workspace_id,
        name=agent.name,
        description=agent.description,
        llm_profile_id=agent.llm_profile_id,
        system_prompt=agent.system_prompt,
        source_prompt_id=agent.source_prompt_id,
        params=agent.params or {},
        structured_output_id=agent.structured_output_id,
        web_search=agent.web_search,
        skill_ids=ids["skill_ids"],
        tool_ids=ids["tool_ids"],
        knowledge_base_ids=ids["knowledge_base_ids"],
        connector_ids=ids["connector_ids"],
        subagent_ids=ids["subagent_ids"],
        resolved=resolved,
        capabilities=capabilities,
        status="needs_attention" if issues else "ready",
        issues=issues,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def _ordered(model, resource_type: str):
    return (
        select(model)
        .outerjoin(
            ResourceUsage,
            and_(
                ResourceUsage.workspace_id == model.workspace_id,
                ResourceUsage.resource_type == resource_type,
                ResourceUsage.resource_id == model.id,
            ),
        )
        .order_by(
            func.coalesce(ResourceUsage.last_used_at, model.created_at).desc(),
            model.name,
        )
    )


@router.get("/options", response_model=AgentOptionsResponse)
async def agent_options(
    workspace_id: str,
    agent_id: str | None = Query(None),
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    profiles = list(
        (
            await db.execute(
                _ordered(LlmProfile, "llm_profile").where(
                    LlmProfile.workspace_id == workspace_id,
                    LlmProfile.status == "verified",
                )
            )
        )
        .scalars()
        .all()
    )
    outputs = list(
        (
            await db.execute(
                _ordered(StructuredOutput, "structured_output").where(
                    StructuredOutput.workspace_id == workspace_id
                )
            )
        )
        .scalars()
        .all()
    )
    skills = list(
        (
            await db.execute(
                _ordered(Skill, "skill").where(Skill.workspace_id == workspace_id)
            )
        )
        .scalars()
        .all()
    )
    knowledge_bases = list(
        (
            await db.execute(
                _ordered(KnowledgeBase, "knowledge_base").where(
                    KnowledgeBase.workspace_id == workspace_id
                )
            )
        )
        .scalars()
        .all()
    )
    connectors = list(
        (
            await db.execute(
                _ordered(ConnectorInstance, "connector").where(
                    ConnectorInstance.workspace_id == workspace_id
                )
            )
        )
        .scalars()
        .all()
    )
    tools = list(
        (
            await db.execute(
                _ordered(Tool, "tool").where(Tool.workspace_id == workspace_id)
            )
        )
        .scalars()
        .all()
    )
    agents_query = _ordered(Agent, "agent").where(Agent.workspace_id == workspace_id)
    if agent_id:
        agents_query = agents_query.where(Agent.id != agent_id)
    agents = list((await db.execute(agents_query)).scalars().all())

    def tool_description(code: str) -> str | None:
        extracted = extract_schema(code)
        return extracted.schema.description if extracted.schema else None

    skill_options = []
    for row in skills:
        references = extract_references(row.content)
        skill_options.append(
            AgentOption(
                id=row.id,
                name=row.name,
                description=row.description,
                skill_refs=references.skill_refs,
                tool_refs=references.tool_refs,
            )
        )

    return AgentOptionsResponse(
        llm_profiles=[
            AgentOption(
                id=row.id,
                name=row.name,
                provider=row.provider,
                model_id=row.model_id,
                status=row.status,
                capabilities=_capabilities_response(row),
            )
            for row in profiles
        ],
        structured_outputs=[
            AgentOption(id=row.id, name=row.name, description=row.description) for row in outputs
        ],
        skills=skill_options,
        knowledge_bases=[AgentOption(id=row.id, name=row.name) for row in knowledge_bases],
        connectors=[
            AgentOption(id=row.id, name=row.name, status=row.status) for row in connectors
        ],
        tools=[
            AgentOption(id=row.id, name=row.name, description=tool_description(row.code))
            for row in tools
        ],
        agents=[
            AgentOption(id=row.id, name=row.name, description=row.description) for row in agents
        ],
    )


@router.get("", response_model=AgentListResponse)
async def list_agents(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Agent)
            .where(Agent.workspace_id == workspace_id)
            .order_by(Agent.updated_at.desc())
        )
    ).scalars().all()

    # shortcut: the badge asks `_to_response` so it can never disagree with the
    # detail view, at the cost of one pass of queries per agent. Paginate or move
    # the checks into one query if a workspace ever holds hundreds of agents.
    items = []
    for agent in rows:
        status = (await _to_response(db, agent)).status
        items.append(
            AgentListItem(
                id=agent.id,
                name=agent.name,
                description=agent.description,
                llm_profile_id=agent.llm_profile_id,
                status=status,
                updated_at=agent.updated_at,
            )
        )
    return AgentListResponse(agents=items, total=len(items))


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    workspace_id: str,
    request: AgentWriteRequest,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    await assert_name_is_free(db, workspace_id, request.name, exclude_id=None)
    try:
        validated = await validate_agent(db, workspace_id, _input(request), agent_id=None)
    except CompositionError as exc:
        _raise_composition(exc)

    agent = Agent(
        workspace_id=workspace_id,
        name=request.name.strip(),
        description=request.description,
        llm_profile_id=validated.profile.id,
        system_prompt=request.system_prompt,
        source_prompt_id=validated.source_prompt.id if validated.source_prompt else None,
        params=validated.params,
        structured_output_id=(
            validated.structured_output.id if validated.structured_output else None
        ),
        web_search=validated.web_search,
        created_by=current_user.id,
    )
    db.add(agent)
    await db.flush()
    _add_joins(db, agent.id, _ids_from_validated(validated))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictException(f'An agent named "{request.name}" already exists.')

    await db.refresh(agent)
    await bump_usage(db, workspace_id, "llm_profile", validated.profile.id)
    await db.commit()
    return await _to_response(db, agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    workspace_id: str,
    agent_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    agent = await _load_agent(db, workspace_id, agent_id)
    return await _to_response(db, agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    workspace_id: str,
    agent_id: str,
    request: AgentWriteRequest,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    agent = await _load_agent(db, workspace_id, agent_id)
    await assert_name_is_free(db, workspace_id, request.name, exclude_id=agent_id)
    try:
        validated = await validate_agent(db, workspace_id, _input(request), agent_id=agent_id)
    except CompositionError as exc:
        _raise_composition(exc)

    agent.name = request.name.strip()
    agent.description = request.description
    agent.llm_profile_id = validated.profile.id
    agent.system_prompt = request.system_prompt
    agent.source_prompt_id = validated.source_prompt.id if validated.source_prompt else None
    agent.params = validated.params
    agent.structured_output_id = (
        validated.structured_output.id if validated.structured_output else None
    )
    agent.web_search = validated.web_search
    await _replace_joins(db, agent.id, _ids_from_validated(validated))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ConflictException(f'An agent named "{request.name}" already exists.')

    await db.refresh(agent)
    await bump_usage(db, workspace_id, "llm_profile", validated.profile.id)
    await db.commit()
    return await _to_response(db, agent)


@router.delete("/{agent_id}")
async def delete_agent(
    workspace_id: str,
    agent_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    agent = await _load_agent(db, workspace_id, agent_id)
    referrers = (
        await db.execute(
            select(Agent.name)
            .join(AgentSubagent, AgentSubagent.agent_id == Agent.id)
            .where(
                AgentSubagent.subagent_id == agent_id,
                Agent.workspace_id == workspace_id,
            )
        )
    ).scalars().all()
    if referrers:
        raise ConflictException(
            "This agent is used as a subagent by: " + ", ".join(sorted(referrers))
        )

    await db.delete(agent)
    await db.commit()
    return {"success": True}


@router.post("/{agent_id}/chat")
async def chat_with_agent(
    workspace_id: str,
    agent_id: str,
    request: AgentChatRequest,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    await _load_agent(db, workspace_id, agent_id)
    messages = [message.model_dump() for message in request.messages]
    execution = Execution(
        workspace_id=workspace_id,
        agent_id=agent_id,
        status="running",
        trigger_type="chat",
        input_data={"messages": messages},
        started_at=datetime.now(timezone.utc),
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    return StreamingResponse(
        _sse(stream_chat(workspace_id, agent_id, messages, execution.id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
