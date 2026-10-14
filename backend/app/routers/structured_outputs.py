from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import logger
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.models.structured_output import StructuredOutput
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.structured_output import (
    ParseSchemaRequest,
    ParseSchemaResponse,
    StructuredOutputCreate,
    StructuredOutputListResponse,
    StructuredOutputResponse,
    StructuredOutputUpdate,
)
from app.services.structured_output import (
    Definition,
    StructuredOutputError,
    compile_schema,
    find_referrers,
    parse_json_schema,
)
from app.utils.errors import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)

router = APIRouter()


def _definition(row: StructuredOutput) -> Definition:
    return Definition(name=row.name, description=row.description, fields=list(row.fields or []))


def _try_compile(
    definition: Definition, workspace_defs: dict[str, Definition]
) -> dict | None:
    try:
        return compile_schema(definition, workspace_defs)
    except StructuredOutputError as exc:
        # Only reachable when a row was changed outside the API. Leave the row
        # readable so it can be repaired instead of locking the page out.
        logger.warning(f"Structured output '{definition.name}' does not compile: {exc}")
        return None


async def _load_rows(db: AsyncSession, workspace_id: str) -> list[StructuredOutput]:
    result = await db.execute(
        select(StructuredOutput)
        .where(StructuredOutput.workspace_id == workspace_id)
        .order_by(StructuredOutput.updated_at.desc())
    )
    return list(result.scalars().all())


async def _load_row(db: AsyncSession, workspace_id: str, output_id: str) -> StructuredOutput:
    result = await db.execute(
        select(StructuredOutput).where(
            StructuredOutput.id == output_id,
            StructuredOutput.workspace_id == workspace_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundException("Structured output")
    return row


def _to_response(
    row: StructuredOutput,
    workspace_defs: dict[str, Definition],
    *,
    with_schema: bool = False,
) -> StructuredOutputResponse:
    definition = _definition(row)
    return StructuredOutputResponse(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        description=row.description,
        fields=definition.fields,
        referenced_by=find_referrers(row.name, workspace_defs),
        compiled_schema=_try_compile(definition, workspace_defs) if with_schema else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _assert_name_is_free(rows: list[StructuredOutput], name: str, *, exclude_id: str | None) -> None:
    wanted = name.lower()
    for row in rows:
        if row.id != exclude_id and row.name.lower() == wanted:
            raise ConflictException(f'A structured output named "{row.name}" already exists.')


def _cascade_rename(rows: list[StructuredOutput], old_name: str, new_name: str) -> None:
    """Point every reference at the new name. ADR-016: references are by name."""
    old = old_name.lower()
    for row in rows:
        rewritten: list[dict] = []
        touched = False
        for field in row.fields or []:
            field = dict(field)
            for key in ("ref", "items_ref"):
                if isinstance(field.get(key), str) and field[key].lower() == old:
                    field[key] = new_name
                    touched = True
            rewritten.append(field)
        if touched:
            # Reassign rather than mutate: SQLAlchemy does not track JSON in place.
            row.fields = rewritten


@router.post("/parse-schema", response_model=ParseSchemaResponse)
async def parse_schema(
    workspace_id: str,
    request: ParseSchemaRequest,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    rows = await _load_rows(db, workspace_id)
    try:
        parsed = parse_json_schema(request.raw_schema, existing_names={row.name for row in rows})
    except StructuredOutputError as exc:
        raise BadRequestException(str(exc)) from exc
    return ParseSchemaResponse(
        fields=parsed.fields, title=parsed.title, description=parsed.description
    )


@router.get("", response_model=StructuredOutputListResponse)
async def list_structured_outputs(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    rows = await _load_rows(db, workspace_id)
    workspace_defs = {row.name: _definition(row) for row in rows}
    outputs = [_to_response(row, workspace_defs) for row in rows]
    return StructuredOutputListResponse(structured_outputs=outputs, total=len(outputs))


@router.post("", response_model=StructuredOutputResponse)
async def create_structured_output(
    workspace_id: str,
    request: StructuredOutputCreate,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    rows = await _load_rows(db, workspace_id)
    _assert_name_is_free(rows, request.name, exclude_id=None)

    definition = Definition(
        name=request.name,
        description=request.description,
        fields=list(request.fields),
    )
    workspace_defs = {row.name: _definition(row) for row in rows}
    workspace_defs[definition.name] = definition

    try:
        compile_schema(definition, workspace_defs)
    except StructuredOutputError as exc:
        raise BadRequestException(str(exc)) from exc

    row = StructuredOutput(
        workspace_id=workspace_id,
        name=definition.name,
        description=definition.description,
        fields=[field.to_storage() for field in definition.fields],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info(f"Structured output '{row.name}' created by user {current_user.id}")

    workspace_defs[row.name] = _definition(row)
    return _to_response(row, workspace_defs, with_schema=True)


@router.get("/{output_id}", response_model=StructuredOutputResponse)
async def get_structured_output(
    workspace_id: str,
    output_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    row = await _load_row(db, workspace_id, output_id)
    rows = await _load_rows(db, workspace_id)
    workspace_defs = {item.name: _definition(item) for item in rows}
    return _to_response(row, workspace_defs, with_schema=True)


@router.put("/{output_id}", response_model=StructuredOutputResponse)
async def update_structured_output(
    workspace_id: str,
    output_id: str,
    request: StructuredOutputUpdate,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    row = await _load_row(db, workspace_id, output_id)
    rows = await _load_rows(db, workspace_id)
    _assert_name_is_free(rows, request.name, exclude_id=row.id)

    old_name = row.name
    definition = Definition(
        name=request.name,
        description=request.description,
        fields=list(request.fields),
    )

    if definition.name != old_name:
        _cascade_rename([item for item in rows if item.id != row.id], old_name, definition.name)

    others = {item.name: _definition(item) for item in rows if item.id != row.id}
    workspace_defs = {**others, definition.name: definition}

    try:
        compile_schema(definition, workspace_defs)
    except StructuredOutputError as exc:
        raise BadRequestException(str(exc)) from exc

    row.name = definition.name
    row.description = definition.description
    row.fields = [field.to_storage() for field in definition.fields]
    db.add(row)
    await db.commit()
    await db.refresh(row)
    if definition.name != old_name:
        logger.info(
            f"Structured output '{old_name}' renamed to '{definition.name}' by user {current_user.id}"
        )
    else:
        logger.info(f"Structured output '{row.name}' updated by user {current_user.id}")

    workspace_defs[row.name] = _definition(row)
    return _to_response(row, workspace_defs, with_schema=True)


@router.delete("/{output_id}")
async def delete_structured_output(
    workspace_id: str,
    output_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    row = await _load_row(db, workspace_id, output_id)
    rows = await _load_rows(db, workspace_id)
    workspace_defs = {item.name: _definition(item) for item in rows}

    referrers = find_referrers(row.name, workspace_defs)
    if referrers:
        raise ConflictException(
            f"Cannot delete: referenced by {', '.join(referrers)}. Remove the reference first."
        )

    await db.delete(row)
    await db.commit()
    logger.info(f"Structured output '{row.name}' deleted")
    return {"success": True}
