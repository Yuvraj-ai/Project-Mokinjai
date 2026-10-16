from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import logger
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.models.skill import Skill
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.skill import (
    ReferenceMenuEntry,
    ReferenceMenuResponse,
    SkillCreate,
    SkillListResponse,
    SkillResponse,
    SkillUpdate,
)
from app.services.skill import (
    SkillDefinition,
    SkillError,
    extract_references,
    find_skill_referrers,
    rewrite_skill_references,
    validate_skill,
)
from app.utils.errors import BadRequestException, ConflictException, NotFoundException

router = APIRouter()


def _definition(row: Skill) -> SkillDefinition:
    return SkillDefinition(name=row.name, description=row.description, content=row.content)


async def _load_rows(db: AsyncSession, workspace_id: str) -> list[Skill]:
    result = await db.execute(
        select(Skill)
        .where(Skill.workspace_id == workspace_id)
        .order_by(Skill.updated_at.desc())
    )
    return list(result.scalars().all())


async def _load_row(db: AsyncSession, workspace_id: str, skill_id: str) -> Skill:
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.workspace_id == workspace_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundException("Skill")
    return row


async def _known_tools(db: AsyncSession, workspace_id: str) -> list[tuple[str, str]]:
    """(name, description) of every tool a `/ToolName` may name in this workspace.

    This is the one place Skills reads the Tools feature: `app.models.tool.Tool`
    (table `tools`) and `app.tools.list_builtin_tools()`. Everything else in this
    module is independent of it.

    Two sources, because both are tools the user sees on the Tools page and
    ADR-021 gives `/` the job of declaring a tool dependency:

    - **Workspace-defined tools**, from the `tools` table. That table stores
      `code` as canonical and derives everything else on read (Tools spec §1 and
      §3), so the description comes from the same extractor the Tools feature
      uses -- there is no `description` column to select.
    - **Built-ins**, from the registry. The Tools spec deliberately exposes
      `list_builtin_tools()` for this merge and leaves the decision to this plan
      (Tools spec, "Owed to other plans", item 2). Without it, built-ins would be
      invisible to `/ToolName` and to autocomplete even though the user is
      looking at them -- and `read_skill` itself lives in that registry.

    A built-in is named by its key (`current_time`), not its display name
    (`Current Time`); the key is the identifier the Tools page shows for
    reference, and the display name is not identifier-shaped.
    """
    from app.models.tool import Tool
    from app.services.tool_schema import extract_schema
    from app.tools import list_builtin_tools

    rows = await db.execute(
        select(Tool.name, Tool.code).where(Tool.workspace_id == workspace_id)
    )

    known: list[tuple[str, str]] = []
    for name, code in rows.all():
        result = extract_schema(code)
        # A stored tool passed extraction at save, so `schema` is not None in
        # practice. The fallback keeps a reference menu from raising on a row
        # that predates a rule change.
        known.append((name, result.schema.description if result.schema else ""))

    known.extend((entry.key, entry.schema.description) for entry in list_builtin_tools())
    return known


def _to_response(row: Skill, workspace_skills: dict[str, SkillDefinition]) -> SkillResponse:
    definition = _definition(row)
    references = extract_references(definition.content)
    return SkillResponse(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        description=row.description,
        content=row.content,
        skill_refs=references.skill_refs,
        tool_refs=references.tool_refs,
        referenced_by=find_skill_referrers(row.name, workspace_skills),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _assert_name_is_free(rows: list[Skill], name: str, *, exclude_id: str | None) -> None:
    wanted = name.lower()
    for row in rows:
        if row.id != exclude_id and row.name.lower() == wanted:
            raise ConflictException(f'A skill named "{row.name}" already exists.')


def _cascade_rename(rows: list[Skill], old_name: str, new_name: str) -> None:
    """Point every `@old_name` at `@new_name`. ADR-019: references are by name.

    The rewrite goes through the same scanner validation uses, so it touches only
    tokens that were references -- never an `@old_name` inside a code fence.
    """
    for row in rows:
        rewritten = rewrite_skill_references(row.content, old_name, new_name)
        if rewritten != row.content:
            row.content = rewritten


@router.get("", response_model=SkillListResponse)
async def list_skills(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    rows = await _load_rows(db, workspace_id)
    workspace_skills = {row.name: _definition(row) for row in rows}
    skills = [_to_response(row, workspace_skills) for row in rows]
    return SkillListResponse(skills=skills, total=len(skills))


# Declared before `/{skill_id}` so the literal path is not read as an id.
@router.get("/reference-menu", response_model=ReferenceMenuResponse)
async def reference_menu(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    rows = await _load_rows(db, workspace_id)
    tools = await _known_tools(db, workspace_id)
    return ReferenceMenuResponse(
        skills=[
            ReferenceMenuEntry(name=row.name, description=row.description) for row in rows
        ],
        tools=[
            ReferenceMenuEntry(name=name, description=description)
            for name, description in tools
        ],
    )


@router.post("", response_model=SkillResponse)
async def create_skill(
    workspace_id: str,
    request: SkillCreate,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    rows = await _load_rows(db, workspace_id)
    _assert_name_is_free(rows, request.name, exclude_id=None)

    definition = SkillDefinition(
        name=request.name, description=request.description, content=request.content
    )
    workspace_skills = {row.name: _definition(row) for row in rows}
    workspace_skills[definition.name] = definition
    known_tools = [name for name, _ in await _known_tools(db, workspace_id)]

    try:
        validate_skill(definition, workspace_skills, known_tools)
    except SkillError as exc:
        raise BadRequestException(str(exc)) from exc

    row = Skill(
        workspace_id=workspace_id,
        name=definition.name,
        description=definition.description,
        content=definition.content,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info(f"Skill '{row.name}' created by user {current_user.id}")

    workspace_skills[row.name] = _definition(row)
    return _to_response(row, workspace_skills)


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    workspace_id: str,
    skill_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    row = await _load_row(db, workspace_id, skill_id)
    rows = await _load_rows(db, workspace_id)
    workspace_skills = {item.name: _definition(item) for item in rows}
    return _to_response(row, workspace_skills)


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    workspace_id: str,
    skill_id: str,
    request: SkillUpdate,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    row = await _load_row(db, workspace_id, skill_id)
    rows = await _load_rows(db, workspace_id)
    _assert_name_is_free(rows, request.name, exclude_id=row.id)

    old_name = row.name
    definition = SkillDefinition(
        name=request.name, description=request.description, content=request.content
    )

    if definition.name != old_name:
        _cascade_rename([item for item in rows if item.id != row.id], old_name, definition.name)

    # Built after the cascade, so the rewrite is what validation sees.
    others = {item.name: _definition(item) for item in rows if item.id != row.id}
    workspace_skills = {**others, definition.name: definition}
    known_tools = [name for name, _ in await _known_tools(db, workspace_id)]

    try:
        validate_skill(definition, workspace_skills, known_tools)
    except SkillError as exc:
        # Nothing is committed before this point, so a rejected update leaves the
        # cascade in memory only and the request's session discards it.
        raise BadRequestException(str(exc)) from exc

    row.name = definition.name
    row.description = definition.description
    row.content = definition.content
    db.add(row)
    await db.commit()
    await db.refresh(row)
    if definition.name != old_name:
        logger.info(f"Skill '{old_name}' renamed to '{definition.name}' by user {current_user.id}")
    else:
        logger.info(f"Skill '{row.name}' updated by user {current_user.id}")

    workspace_skills[row.name] = _definition(row)
    return _to_response(row, workspace_skills)


@router.delete("/{skill_id}")
async def delete_skill(
    workspace_id: str,
    skill_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    row = await _load_row(db, workspace_id, skill_id)
    rows = await _load_rows(db, workspace_id)
    workspace_skills = {item.name: _definition(item) for item in rows}

    referrers = find_skill_referrers(row.name, workspace_skills)
    if referrers:
        raise ConflictException(
            f"Cannot delete: referenced by {', '.join(referrers)}. Remove the reference first."
        )

    await db.delete(row)
    await db.commit()
    logger.info(f"Skill '{row.name}' deleted")
    return {"success": True}
