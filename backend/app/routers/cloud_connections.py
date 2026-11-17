"""Cloud connection routes. User-scoped: a token belongs to the person who granted it."""

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.cloud_connection import CloudConnection
from app.models.user import User
from app.services import cloud_connections as connection_store
from app.services import onedrive

router = APIRouter()


@router.get("/onedrive/authorize")
async def authorize_onedrive(current_user: User = Depends(get_current_user)) -> dict:
    return {"url": onedrive.authorize_url(current_user.id)}


@router.get("/onedrive/callback")
async def onedrive_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """No auth dependency: a browser arrives here, and identity travels in `state`."""
    frontend = get_settings().FRONTEND_URL
    failed = RedirectResponse(f"{frontend}/files?onedrive=failed", status_code=302)
    if error or not code or not state:
        return failed

    try:
        payload = onedrive.decode_state(state)
    except onedrive.OneDriveAuthError:
        raise HTTPException(status_code=400, detail="invalid OAuth state")

    try:
        tokens = await onedrive.exchange_code(code)
    except onedrive.OneDriveAuthError:
        return failed

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return failed
    await connection_store.save_connection(
        db,
        user_id=payload["sub"],
        provider="onedrive",
        refresh_token=refresh_token,
        account_label=None,
    )
    return RedirectResponse(f"{frontend}/files?onedrive=connected", status_code=302)


@router.get("/onedrive/items")
async def list_onedrive_items(
    item_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    connection = await connection_store.get_connection(
        db, user_id=current_user.id, provider="onedrive"
    )
    if connection is None:
        raise HTTPException(status_code=409, detail="Connect OneDrive first")
    try:
        items = await onedrive.list_items(db, connection, item_id=item_id)
    except onedrive.OneDriveAuthError:
        raise HTTPException(status_code=409, detail="Reconnect OneDrive")
    return {"items": items}


@router.get("")
async def list_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Never returns a token. Google stores nothing, so it never appears here."""
    rows = (
        await db.execute(
            select(CloudConnection).where(CloudConnection.user_id == current_user.id)
        )
    ).scalars()
    return [
        {
            "provider": row.provider,
            "account_label": row.account_label,
            "connected_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.delete("/{provider}", status_code=204)
async def delete_connection(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await connection_store.delete_connection(
        db, user_id=current_user.id, provider=provider
    )
    return Response(status_code=204)
