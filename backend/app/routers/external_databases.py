"""External database connection records (ADR-012).

The URI is a credential: encrypted at rest and never returned. A record is not a
connection — creating one contacts nothing, and no driver is imported for any kind.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import encrypt_api_key
from app.database import get_db
from app.logging import logger
from app.middleware.rbac import require_workspace_role
from app.models.external_database import KINDS, ExternalDatabaseConnection
from app.models.workspace import WorkspaceMember
from app.schemas.external_database import (
    ExternalDatabaseCreate,
    ExternalDatabaseListResponse,
    ExternalDatabaseResponse,
    ExternalDatabaseUpdate,
)
from app.utils.errors import BadRequestException, NotFoundException

router = APIRouter()

# Which target fields each kind uses. `kind` is a label and a validation hint — it never
# selects a driver (ADR-012) — so this table is the only place it is consulted.
_TARGET_RULES = {
    "postgres": {"database_name": "required", "collection_name": "forbidden"},
    "mysql": {"database_name": "required", "collection_name": "forbidden"},
    "mongodb": {"database_name": "required", "collection_name": "optional"},
    "chromadb": {"database_name": "optional", "collection_name": "required"},
}


def _blank_to_none(value: str | None) -> str | None:
    """An empty form field behaves like an omitted one."""
    if value is None:
        return None
    return value.strip() or None


def _validate_kind(kind: str) -> None:
    if kind not in KINDS:
        raise BadRequestException(
            f"Unsupported kind {kind!r}; expected one of {', '.join(KINDS)}"
        )


def _validate_uri(uri: str) -> None:
    if "://" not in uri:
        raise BadRequestException(
            "A URI with a scheme is required, for example postgresql://user@host:5432/db"
        )


def _validate_targets(kind: str, database_name: str | None, collection_name: str | None) -> None:
    rules = _TARGET_RULES[kind]
    for field, value in (("database_name", database_name), ("collection_name", collection_name)):
        if rules[field] == "required" and value is None:
            raise BadRequestException(f"A {kind} connection requires {field}")
        if rules[field] == "forbidden" and value is not None:
            raise BadRequestException(f"A {kind} connection uses database_name, not {field}")


def _to_response(row: ExternalDatabaseConnection) -> ExternalDatabaseResponse:
    return ExternalDatabaseResponse(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        kind=row.kind,
        database_name=row.database_name,
        collection_name=row.collection_name,
        # The URI is never returned, in any form, by any endpoint. A boolean is all a
        # caller learns — the same contract as LlmProfileResponse.has_api_key.
        has_uri=True,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _load(
    db: AsyncSession, workspace_id: str, connection_id: str
) -> ExternalDatabaseConnection:
    result = await db.execute(
        select(ExternalDatabaseConnection).where(
            ExternalDatabaseConnection.id == connection_id,
            ExternalDatabaseConnection.workspace_id == workspace_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundException("External database connection")
    return row


@router.post("", response_model=ExternalDatabaseResponse, status_code=201)
async def create_external_database(
    workspace_id: str,
    request: ExternalDatabaseCreate,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    database_name = _blank_to_none(request.database_name)
    collection_name = _blank_to_none(request.collection_name)
    uri = request.uri.strip()

    _validate_kind(request.kind)
    _validate_uri(uri)
    _validate_targets(request.kind, database_name, collection_name)

    row = ExternalDatabaseConnection(
        workspace_id=workspace_id,
        name=request.name,
        kind=request.kind,
        encrypted_uri=encrypt_api_key(uri),
        database_name=database_name,
        collection_name=collection_name,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info(f"External database connection {row.id} created (kind={row.kind})")
    return _to_response(row)


@router.get("", response_model=ExternalDatabaseListResponse)
async def list_external_databases(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    filters = [ExternalDatabaseConnection.workspace_id == workspace_id]
    total = (
        await db.execute(
            select(func.count()).select_from(ExternalDatabaseConnection).where(*filters)
        )
    ).scalar_one()
    result = await db.execute(
        select(ExternalDatabaseConnection)
        .where(*filters)
        .order_by(ExternalDatabaseConnection.created_at.desc())
    )
    return ExternalDatabaseListResponse(
        connections=[_to_response(row) for row in result.scalars().all()],
        total=total,
    )


@router.get("/{connection_id}", response_model=ExternalDatabaseResponse)
async def get_external_database(
    workspace_id: str,
    connection_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    return _to_response(await _load(db, workspace_id, connection_id))


@router.patch("/{connection_id}", response_model=ExternalDatabaseResponse)
async def update_external_database(
    workspace_id: str,
    connection_id: str,
    request: ExternalDatabaseUpdate,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    row = await _load(db, workspace_id, connection_id)

    kind = request.kind if request.kind is not None else row.kind
    database_name = (
        _blank_to_none(request.database_name)
        if request.database_name is not None
        else row.database_name
    )
    collection_name = (
        _blank_to_none(request.collection_name)
        if request.collection_name is not None
        else row.collection_name
    )
    uri = _blank_to_none(request.uri)

    _validate_kind(kind)
    if uri is not None:
        _validate_uri(uri)
    _validate_targets(kind, database_name, collection_name)

    row.name = request.name if request.name is not None else row.name
    row.kind = kind
    row.database_name = database_name
    row.collection_name = collection_name
    if uri is not None:
        # A blank or omitted URI keeps the stored ciphertext, exactly as a blank API key
        # does on an LLM profile retest (routers/llm_profiles.py:86-90).
        row.encrypted_uri = encrypt_api_key(uri)

    await db.commit()
    await db.refresh(row)
    logger.info(f"External database connection {row.id} updated")
    return _to_response(row)


@router.delete("/{connection_id}")
async def delete_external_database(
    workspace_id: str,
    connection_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    row = await _load(db, workspace_id, connection_id)
    await db.delete(row)
    await db.commit()
    logger.info(f"External database connection {connection_id} deleted")
    return {"success": True}
