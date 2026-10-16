"""Tools: built-in registry entries, and Python functions this workspace owns.

A user-defined tool's code is canonical. Its name, description, parameter list and
JSON Schema are extracted from that code on read, so none of them can drift from
the function the model will actually call.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import logger
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.models.skill import Skill
from app.models.tool import Tool
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.tool import (
    BuiltinToolListResponse,
    BuiltinToolResponse,
    ToolListResponse,
    ToolResponse,
    ToolSchema,
    ToolSchemaResponse,
    ToolValidateResponse,
    ToolWriteRequest,
)
from app.services.skill import extract_references
from app.services.tool_schema import compile_input_schema, extract_schema
from app.tools import BUILTIN_TOOLS, list_builtin_tools
from app.utils.errors import BadRequestException, ConflictException, NotFoundException

router = APIRouter()


def _extracted(row: Tool) -> ToolSchema | None:
    """The schema this row's code describes, or None if it no longer extracts.

    A row only ever stores code that passed extraction, so None is reachable only
    when a row was changed outside the API. The row stays readable rather than
    failing the whole page, exactly as an uncompilable structured output does.
    """
    result = extract_schema(row.code)
    if result.schema is None:
        logger.warning(f"Tool {row.id} does not extract: {' '.join(result.errors)}")
        return None
    return result.schema


def _to_response(row: Tool) -> ToolResponse:
    schema = _extracted(row)
    return ToolResponse(
        id=row.id,
        workspace_id=row.workspace_id,
        name=schema.name if schema else row.name,
        description=schema.description if schema else "",
        code=row.code,
        parameters=schema.parameters if schema else [],
        returns=schema.returns if schema else "any",
        input_schema=compile_input_schema(schema) if schema else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _load_rows(db: AsyncSession, workspace_id: str) -> list[Tool]:
    result = await db.execute(
        select(Tool)
        .where(Tool.workspace_id == workspace_id)
        .order_by(Tool.updated_at.desc())
    )
    return list(result.scalars().all())


async def _load_row(db: AsyncSession, workspace_id: str, tool_id: str) -> Tool:
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id, Tool.workspace_id == workspace_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundException("Tool")
    return row


async def _skill_referrers(db: AsyncSession, workspace_id: str, tool_name: str) -> list[str]:
    """Names of workspace skills whose content references `tool_name` with a `/`."""
    wanted = tool_name.lower()
    rows = (
        await db.execute(
            select(Skill.name, Skill.content).where(Skill.workspace_id == workspace_id)
        )
    ).all()
    return sorted(
        name
        for name, content in rows
        if any(ref.lower() == wanted for ref in extract_references(content).tool_refs)
    )


def _assert_name_is_free(rows: list[Tool], name: str, *, exclude_id: str | None) -> None:
    """A name must be free in the workspace, and must not shadow a built-in.

    A built-in's key is what a skill's `/ToolName` and the runtime resolve, so a
    custom tool that took one would make that resolution ambiguous. Only the key is
    compared: a display name like "Current Time" is not an identifier and cannot be
    a function name in the first place.
    """
    if name.lower() in {key.lower() for key in BUILTIN_TOOLS}:
        raise ConflictException(
            f'"{name}" is a built-in tool. A custom tool cannot use its name.'
        )

    wanted = name.lower()
    for row in rows:
        if row.id != exclude_id and row.name.lower() == wanted:
            raise ConflictException(f'A tool named "{row.name}" already exists.')


@router.get("/builtin", response_model=BuiltinToolListResponse)
async def list_builtins(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
):
    """The built-in tools, from the registry.

    ADR-015: name and description only. A built-in has no row, no workspace and no
    edit path — it is backend code — and its source never leaves the process. Its
    input schema stays in the registry, where agent construction reads it.
    """
    tools = [
        BuiltinToolResponse(
            built_in_key=entry.key, name=entry.name, description=entry.description
        )
        for entry in list_builtin_tools()
    ]
    return BuiltinToolListResponse(tools=tools, total=len(tools))


@router.post("/validate", response_model=ToolValidateResponse)
async def validate_tool(
    workspace_id: str,
    request: ToolWriteRequest,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
):
    """Extract a schema from code without saving it — the whole live preview.

    Answers with the errors instead of raising them: the editor calls this after
    every typing pause, and "this code has no `Args:` section" is the answer to the
    question asked, not a failed request. There is no database dependency here at
    all: nothing is read and nothing is written.
    """
    result = extract_schema(request.code)
    if result.schema is None:
        return ToolValidateResponse(valid=False, errors=result.errors)

    schema = result.schema
    return ToolValidateResponse(
        valid=True,
        schema=ToolSchemaResponse(
            name=schema.name,
            description=schema.description,
            parameters=schema.parameters,
            returns=schema.returns,
            input_schema=compile_input_schema(schema),
        ),
    )


@router.get("", response_model=ToolListResponse)
async def list_tools(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    rows = await _load_rows(db, workspace_id)
    tools = [_to_response(row) for row in rows]
    return ToolListResponse(tools=tools, total=len(tools))


@router.post("", response_model=ToolResponse)
async def create_tool(
    workspace_id: str,
    request: ToolWriteRequest,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Store a tool. Its name, description and schema all come from the code."""
    result = extract_schema(request.code)
    if result.schema is None:
        raise BadRequestException(" ".join(result.errors))

    rows = await _load_rows(db, workspace_id)
    _assert_name_is_free(rows, result.schema.name, exclude_id=None)

    row = Tool(workspace_id=workspace_id, name=result.schema.name, code=request.code)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info(f"Tool '{row.name}' created by user {current_user.id}")
    return _to_response(row)


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    workspace_id: str,
    tool_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    return _to_response(await _load_row(db, workspace_id, tool_id))


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    workspace_id: str,
    tool_id: str,
    request: ToolWriteRequest,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Replace a tool's code. Renaming the function renames the tool.

    Nothing cascades. No resource references a tool by name yet — a skill's
    `/ToolName` is the first that will — and per ADR-009 an agent built with this
    tool keeps the descriptor and the code it was frozen with until it is rebuilt.
    """
    row = await _load_row(db, workspace_id, tool_id)

    result = extract_schema(request.code)
    if result.schema is None:
        raise BadRequestException(" ".join(result.errors))

    rows = await _load_rows(db, workspace_id)
    _assert_name_is_free(rows, result.schema.name, exclude_id=row.id)

    old_name = row.name
    row.name = result.schema.name
    row.code = request.code
    db.add(row)
    await db.commit()
    await db.refresh(row)
    if row.name != old_name:
        logger.info(f"Tool '{old_name}' renamed to '{row.name}' by user {current_user.id}")
    else:
        logger.info(f"Tool '{row.name}' updated by user {current_user.id}")
    return _to_response(row)


@router.delete("/{tool_id}")
async def delete_tool(
    workspace_id: str,
    tool_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Delete a tool.

    A tool a skill's `/ToolName` points at is refused here with 409, the way
    `/structured-outputs` refuses a referenced definition: the reference would
    dangle, and the autocomplete menu would name a tool the workspace no longer
    has. Remove the reference first.
    """
    row = await _load_row(db, workspace_id, tool_id)

    referrers = await _skill_referrers(db, workspace_id, row.name)
    if referrers:
        raise ConflictException(
            f"Cannot delete: referenced by {', '.join(referrers)}. Remove the reference first."
        )

    await db.delete(row)
    await db.commit()
    logger.info(f"Tool '{row.name}' deleted")
    return {"success": True}
