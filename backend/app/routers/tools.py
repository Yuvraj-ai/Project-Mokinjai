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
from app.middleware.rbac import require_workspace_role
from app.models.tool import Tool
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
from app.services.tool_schema import compile_input_schema, extract_schema
from app.tools import BUILTIN_TOOLS, list_builtin_tools

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
