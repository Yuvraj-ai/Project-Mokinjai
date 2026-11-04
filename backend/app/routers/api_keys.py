"""API key management (plan Task 2) — the dashboard surface.

Editor for writes, viewer for reads. Plaintext appears exactly once (create
and rotate). DELETE is a soft revoke: the row stays as the audit trace.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging import logger
from app.middleware.rbac import require_workspace_role
from app.models.api_key import ApiKey
from app.models.execution import Execution
from app.models.workspace import WorkspaceMember
from app.schemas.api_key import (
    ApiKeyCreatedResponse,
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyUpdate,
    ApiKeyUsageResponse,
    DailySpend,
)
from app.services.api_keys import (
    RESET_PERIODS,
    audit,
    create_key,
    rotate_key,
    spend_in_window,
)
from app.utils.errors import NotFoundException

router = APIRouter()


def _status(key: ApiKey) -> str:
    now = datetime.now(timezone.utc)
    if key.revoked_at is not None:
        return "revoked"
    if key.disabled_at is not None:
        return "disabled"
    if key.expires_at is not None and key.expires_at <= now:
        return "expired"
    return "active"


def _to_response(key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=key.id,
        workspace_id=key.workspace_id,
        name=key.name,
        prefix=key.prefix,
        description=key.description,
        status=_status(key),
        credit_limit_usd=key.credit_limit_usd,
        credit_reset_period=key.credit_reset_period,
        spend_window_started_at=key.spend_window_started_at,
        created_at=key.created_at,
        created_by=key.created_by,
        expires_at=key.expires_at,
        last_used_at=key.last_used_at,
    )


async def _load_key(
    db: AsyncSession, workspace_id: str, key_id: str
) -> ApiKey:
    key = (
        await db.execute(
            select(ApiKey).where(
                ApiKey.id == key_id, ApiKey.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if key is None:
        raise NotFoundException("API key")
    return key


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    workspace_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    keys = (
        (
            await db.execute(
                select(ApiKey)
                .where(ApiKey.workspace_id == workspace_id, ApiKey.revoked_at.is_(None))
                .order_by(ApiKey.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_to_response(key) for key in keys]


@router.post("", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    workspace_id: str,
    request: ApiKeyCreate,
    member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    key, plaintext = await create_key(
        db,
        workspace_id=workspace_id,
        user_id=member.user_id,
        name=request.name,
        expires_at=request.expires_at,
        credit_limit_usd=request.credit_limit_usd,
        credit_reset_period=request.credit_reset_period,
        description=request.description,
    )
    await db.commit()
    await db.refresh(key)
    logger.info(f"API key {key.id} created in workspace {workspace_id}")
    response = ApiKeyCreatedResponse(**_to_response(key).model_dump(), key=plaintext)
    return response


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    workspace_id: str,
    key_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    return _to_response(await _load_key(db, workspace_id, key_id))


@router.patch("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    workspace_id: str,
    key_id: str,
    request: ApiKeyUpdate,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    key = await _load_key(db, workspace_id, key_id)
    if request.name is not None:
        key.name = request.name
    if request.credit_limit_usd is not None or (
        request.credit_limit_usd is None and "credit_limit_usd" in request.model_fields_set
    ):
        key.credit_limit_usd = request.credit_limit_usd
    if request.credit_reset_period is not None or (
        "credit_reset_period" in request.model_fields_set
    ):
        key.credit_reset_period = request.credit_reset_period
        key.spend_window_started_at = datetime.now(timezone.utc)
    if request.description is not None or "description" in request.model_fields_set:
        key.description = request.description
    await db.commit()
    await db.refresh(key)
    return _to_response(key)


@router.get("/{key_id}/usage", response_model=ApiKeyUsageResponse)
async def get_api_key_usage(
    workspace_id: str,
    key_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    key = await _load_key(db, workspace_id, key_id)
    now = datetime.now(timezone.utc)
    window_spend = await spend_in_window(db, key)

    async def total(since: datetime | None) -> float:
        query = select(func.coalesce(func.sum(Execution.cost_usd), 0)).where(
            Execution.api_key_id == key_id, Execution.status == "completed"
        )
        if since is not None:
            query = query.where(Execution.created_at >= since)
        return float((await db.execute(query)).scalar_one() or 0.0)

    daily_rows = (
        await db.execute(
            select(Execution.created_at, Execution.cost_usd).where(
                Execution.api_key_id == key_id,
                Execution.status == "completed",
                Execution.created_at >= now - timedelta(days=30),
            )
        )
    ).all()
    buckets: dict[str, float] = {}
    for created, cost in daily_rows:
        day = created.astimezone(timezone.utc).date().isoformat()
        buckets[day] = buckets.get(day, 0.0) + float(cost or 0)
    daily = [
        DailySpend(date=(now - timedelta(days=offset)).date().isoformat(), cost=0.0)
        for offset in range(29, -1, -1)
    ]
    for entry in daily:
        entry.cost = round(buckets.get(entry.date, 0.0), 6)

    return ApiKeyUsageResponse(
        window_spend=float(window_spend),
        window_limit=float(key.credit_limit_usd) if key.credit_limit_usd is not None else None,
        window_started_at=key.spend_window_started_at,
        totals={
            "today": await total(now.replace(hour=0, minute=0, second=0, microsecond=0)),
            "week": await total(now - timedelta(days=7)),
            "month": await total(now - timedelta(days=30)),
            "total": await total(None),
        },
        daily=daily,
    )


@router.post("/{key_id}/rotate", response_model=ApiKeyCreatedResponse)
async def rotate_api_key(
    workspace_id: str,
    key_id: str,
    member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    key = await _load_key(db, workspace_id, key_id)
    plaintext = await rotate_key(db, key, member.user_id)
    await db.commit()
    await db.refresh(key)
    logger.info(f"API key {key.id} rotated")
    return ApiKeyCreatedResponse(**_to_response(key).model_dump(), key=plaintext)


@router.post("/{key_id}/disable", response_model=ApiKeyResponse)
async def disable_api_key(
    workspace_id: str,
    key_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    key = await _load_key(db, workspace_id, key_id)
    key.disabled_at = datetime.now(timezone.utc)
    await audit(db, workspace_id, "disabled", key)
    await db.commit()
    await db.refresh(key)
    return _to_response(key)


@router.post("/{key_id}/enable", response_model=ApiKeyResponse)
async def enable_api_key(
    workspace_id: str,
    key_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    key = await _load_key(db, workspace_id, key_id)
    key.disabled_at = None
    await audit(db, workspace_id, "enabled", key)
    await db.commit()
    await db.refresh(key)
    return _to_response(key)


@router.delete("/{key_id}")
async def revoke_api_key(
    workspace_id: str,
    key_id: str,
    _member: WorkspaceMember = Depends(require_workspace_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    key = await _load_key(db, workspace_id, key_id)
    key.revoked_at = datetime.now(timezone.utc)
    await audit(db, workspace_id, "revoked", key)
    await db.commit()
    logger.info(f"API key {key_id} revoked")
    return {"success": True}
