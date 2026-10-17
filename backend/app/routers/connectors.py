from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import encrypt_api_key
from app.services.connector_runtime import ConnectorProbeError, probe_connector_tools
from app.database import get_db
from app.logging import logger
from app.middleware.auth import get_current_user
from app.middleware.rbac import require_workspace_role
from app.models.connector import ConnectorInstance
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.connector import (
    CatalogEntryResponse,
    CatalogResponse,
    ConnectorCreate,
    ConnectorUpdate,
    ConnectorListResponse,
    ConnectorResponse,
)
from app.services.connector_catalog import CatalogEntry, get_entry, list_entries
from app.utils.errors import BadRequestException, ConflictException, NotFoundException

router = APIRouter()


def _entry_for(connector_type: str) -> CatalogEntry:
    entry = get_entry(connector_type)
    if entry is None:
        raise BadRequestException(f"Unknown connector type: {connector_type}")
    return entry


def _assert_supported(entry: CatalogEntry) -> None:
    """OAuth is declared in the catalog and refused on every write path.

    Refusing rather than hiding the entries means the catalog stays a complete
    statement of what exists, and adding OAuth later changes this one predicate.
    """
    if entry.auth_type == "oauth":
        raise BadRequestException(
            f"{entry.display_name} signs in with OAuth, which is not supported yet."
        )


def _assert_config_is_complete(entry: CatalogEntry, config: dict) -> None:
    allowed = set(entry.config_fields)
    unknown = sorted(set(config) - allowed)
    if unknown:
        raise BadRequestException(
            f"{entry.display_name} does not accept {', '.join(unknown)} in its configuration."
        )
    for field in entry.config_fields:
        value = config.get(field)
        if not isinstance(value, str) or not value.strip():
            raise BadRequestException(
                f"{entry.display_name} requires '{field}' in its configuration."
            )


def _assert_secret_matches(entry: CatalogEntry, secret: str, *, is_update: bool = False) -> None:
    if entry.auth_type == "none":
        if secret:
            raise BadRequestException(f"{entry.display_name} does not take a secret.")
        return
    if not secret and not is_update:
        raise BadRequestException(f"{entry.secret_label or 'A secret'} is required.")


def _to_response(instance: ConnectorInstance) -> ConnectorResponse:
    entry = get_entry(instance.connector_type)
    return ConnectorResponse(
        id=instance.id,
        workspace_id=instance.workspace_id,
        connector_type=instance.connector_type,
        # A catalog entry that has been renamed or removed must not take the list
        # down with it: the row is still returned, labelled with what it claims.
        display_name=entry.display_name if entry else instance.connector_type,
        name=instance.name,
        transport=entry.transport if entry else "unknown",
        auth_type=entry.auth_type if entry else "unknown",
        auth_scope=instance.auth_scope,
        status=instance.status,
        has_auth=instance.auth_encrypted is not None,
        config=dict(instance.config or {}),
        tools=list(instance.tool_names or []),
        last_error=instance.last_error,
        last_tested_at=instance.last_tested_at,
        created_at=instance.created_at,
        updated_at=instance.updated_at,
    )


async def _load_rows(db: AsyncSession, workspace_id: str) -> list[ConnectorInstance]:
    result = await db.execute(
        select(ConnectorInstance)
        .where(ConnectorInstance.workspace_id == workspace_id)
        .order_by(ConnectorInstance.created_at.desc())
    )
    return list(result.scalars().all())


def _assert_name_is_free(
    rows: list[ConnectorInstance], name: str, *, exclude_id: str | None
) -> None:
    wanted = name.lower()
    for row in rows:
        if row.id != exclude_id and row.name.lower() == wanted:
            raise ConflictException(f'A connector named "{row.name}" already exists.')


async def _load_instance(
    db: AsyncSession, workspace_id: str, connector_id: str
) -> ConnectorInstance:
    result = await db.execute(
        select(ConnectorInstance).where(
            ConnectorInstance.id == connector_id,
            ConnectorInstance.workspace_id == workspace_id,
        )
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise NotFoundException("Connector")
    return instance


@router.get("/catalog", response_model=CatalogResponse)
async def get_connector_catalog(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
):
    """The connectors a user may enable.

    Declared before `/{connector_id}` so the literal path wins the match.
    """
    entries = [
        CatalogEntryResponse(
            id=entry.id,
            display_name=entry.display_name,
            description=entry.description,
            transport=entry.transport,
            auth_type=entry.auth_type,
            secret_label=entry.secret_label,
            config_fields=list(entry.config_fields),
            docs_url=entry.docs_url,
        )
        for entry in list_entries()
    ]
    return CatalogResponse(entries=entries, total=len(entries))


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    workspace_id: str,
    usable: bool = Query(False),
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """`usable=true` returns only enabled connectors — the same parameter and meaning
    as `llm-profiles`, so agent construction reads one convention."""
    filters = [ConnectorInstance.workspace_id == workspace_id]
    if usable:
        filters.append(ConnectorInstance.status == "enabled")
    count_result = await db.execute(
        select(func.count()).select_from(ConnectorInstance).where(*filters)
    )
    total = count_result.scalar_one()
    result = await db.execute(
        select(ConnectorInstance).where(*filters).order_by(ConnectorInstance.created_at.desc())
    )
    connectors = [_to_response(row) for row in result.scalars().all()]
    return ConnectorListResponse(connectors=connectors, total=total)


@router.post("", response_model=ConnectorResponse, status_code=201)
async def create_connector(
    workspace_id: str,
    request: ConnectorCreate,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Record a connector. It is created `pending`; enabling it is a successful test."""
    entry = _entry_for(request.connector_type)
    _assert_supported(entry)

    rows = await _load_rows(db, workspace_id)
    _assert_name_is_free(rows, request.name, exclude_id=None)

    secret = request.auth_secret.strip()
    _assert_secret_matches(entry, secret)
    _assert_config_is_complete(entry, request.config)

    instance = ConnectorInstance(
        workspace_id=workspace_id,
        connector_type=entry.id,
        name=request.name,
        status="pending",
        auth_scope="workspace",
        auth_encrypted=encrypt_api_key(secret) if secret else None,
        config=dict(request.config),
        tool_names=[],
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    logger.info(
        f"Connector instance {instance.id} ({entry.id}) created by user {current_user.id}"
    )
    return _to_response(instance)


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    workspace_id: str,
    connector_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    instance = await _load_instance(db, workspace_id, connector_id)
    return _to_response(instance)


@router.put("/{connector_id}", response_model=ConnectorResponse)
async def update_connector(
    workspace_id: str,
    connector_id: str,
    request: ConnectorUpdate,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    instance = await _load_instance(db, workspace_id, connector_id)
    entry = _entry_for(instance.connector_type)
    _assert_supported(entry)

    rows = await _load_rows(db, workspace_id)
    _assert_name_is_free(rows, request.name, exclude_id=instance.id)

    secret = request.auth_secret.strip()
    _assert_secret_matches(entry, secret, is_update=True)
    _assert_config_is_complete(entry, request.config)

    # `status`, `tool_names` and `last_error` describe one (auth, config) pair, so a
    # verified state that no longer matches what is stored is a claim the row cannot
    # support. A blank secret leaves the ciphertext alone, and asking whether one was
    # submitted is exact without decrypting anything: a new non-blank secret always
    # yields new ciphertext, and a blank one leaves the existing bytes untouched.
    changed = bool(secret) or dict(request.config) != dict(instance.config or {})

    instance.name = request.name
    if secret:
        instance.auth_encrypted = encrypt_api_key(secret)
    # Reassign rather than mutate: SQLAlchemy does not track JSONB in place.
    instance.config = dict(request.config)
    if changed:
        instance.status = "pending"
        instance.tool_names = []
        instance.last_error = None
        instance.last_tested_at = None

    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    logger.info(f"Connector instance {instance.id} updated by user {current_user.id}")
    return _to_response(instance)


@router.delete("/{connector_id}")
async def delete_connector(
    workspace_id: str,
    connector_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Remove the row.

    A real delete, matching `llm_profiles` and `structured_outputs`. The argument the
    other way is recorded in the spec: if Phase 3 resolves connector credentials by
    joining live rows, this is what would turn a working agent into a failing one, and
    the additive fix would be a `deleted_at` column plus a filter on every read.
    """
    instance = await _load_instance(db, workspace_id, connector_id)
    await db.delete(instance)
    await db.commit()
    logger.info(f"Connector instance {instance.id} deleted")
    return {"success": True}


@router.post("/{connector_id}/test", response_model=ConnectorResponse)
async def test_connector(
    workspace_id: str,
    connector_id: str,
    current_user: User = Depends(get_current_user),
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Probe the server and record what it answered.

    200 either way: a server that does not answer is a result to persist and show, not a
    failed request — the same shape as an LLM profile's failed connection test. Enabling
    is testing successfully; there is no second flag that can disagree with `status`.
    """
    instance = await _load_instance(db, workspace_id, connector_id)
    entry = _entry_for(instance.connector_type)
    _assert_supported(entry)

    try:
        tools = await probe_connector_tools(instance)
    except ConnectorProbeError as exc:
        instance.status = "error"
        instance.last_error = str(exc)
        instance.tool_names = []
    else:
        instance.status = "enabled"
        instance.last_error = None
        instance.tool_names = tools

    instance.last_tested_at = datetime.now(timezone.utc)
    db.add(instance)
    await db.commit()
    await db.refresh(instance)
    logger.info(
        f"Connector instance {instance.id} tested by user {current_user.id}: "
        f"{instance.status} ({len(instance.tool_names)} tools)"
    )
    return _to_response(instance)

