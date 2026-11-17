"""Microsoft identity and Graph: the OneDrive half of cloud imports only.

Tenant is `common`: one app registration serves personal and work accounts, and a
single-tenant app would silently exclude one of them. No token is ever logged.
"""

from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

import httpx
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crypto import decrypt_api_key
from app.models.cloud_connection import CloudConnection
from app.services import cloud_connections as connection_store

AUTHORIZE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_URL = "https://graph.microsoft.com/v1.0"
SCOPES = "Files.Read offline_access"
STATE_PURPOSE = "oauth_state"
STATE_TTL_MINUTES = 10


class OneDriveAuthError(Exception):
    """The provider refused the code or the refresh token."""


def build_state(user_id: str) -> str:
    """A short-lived JWT. Not an access token: its purpose claim keeps it unusable."""
    settings = get_settings()
    return jwt.encode(
        {
            "sub": user_id,
            "purpose": STATE_PURPOSE,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_state(state: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            state, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError as exc:
        raise OneDriveAuthError("invalid OAuth state") from exc
    if payload.get("purpose") != STATE_PURPOSE or not payload.get("sub"):
        raise OneDriveAuthError("invalid OAuth state")
    return payload


def authorize_url(user_id: str) -> str:
    settings = get_settings()
    query = urlencode(
        {
            "client_id": settings.MS_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.MS_REDIRECT_URI,
            "response_mode": "query",
            "scope": SCOPES,
            "state": build_state(user_id),
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


async def _post_token(data: dict, transport: httpx.AsyncBaseTransport | None) -> dict:
    async with httpx.AsyncClient(
        transport=transport, timeout=httpx.Timeout(connect=10, read=30, write=30, pool=10)
    ) as client:
        response = await client.post(TOKEN_URL, data=data)
    if response.status_code != 200:
        raise OneDriveAuthError("the provider refused the token request")
    return response.json()


async def exchange_code(
    code: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> dict:
    settings = get_settings()
    return await _post_token(
        {
            "client_id": settings.MS_CLIENT_ID,
            "client_secret": settings.MS_CLIENT_SECRET,
            "redirect_uri": settings.MS_REDIRECT_URI,
            "grant_type": "authorization_code",
            "code": code,
        },
        transport,
    )


async def refresh_access_token(
    refresh_token: str, *, transport: httpx.AsyncBaseTransport | None = None
) -> tuple[str, str | None]:
    """`(access_token, rotated_refresh_token_or_None)`; the caller persists a rotation."""
    settings = get_settings()
    payload = await _post_token(
        {
            "client_id": settings.MS_CLIENT_ID,
            "client_secret": settings.MS_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": SCOPES,
        },
        transport,
    )
    return payload["access_token"], payload.get("refresh_token")


async def access_token_for(
    db: AsyncSession,
    connection: CloudConnection,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Refresh once, and write back a rotated refresh token before using the access."""
    current = decrypt_api_key(connection.refresh_token_encrypted)
    access, rotated = await refresh_access_token(current, transport=transport)
    if rotated and rotated != current:
        await connection_store.save_connection(
            db,
            user_id=connection.user_id,
            provider=connection.provider,
            refresh_token=rotated,
            account_label=connection.account_label,
        )
    return access


async def _children(
    access_token: str,
    item_id: str | None,
    transport: httpx.AsyncBaseTransport | None,
) -> httpx.Response:
    path = (
        f"/me/drive/items/{item_id}/children"
        if item_id
        else "/me/drive/root/children"
    )
    async with httpx.AsyncClient(
        transport=transport, timeout=httpx.Timeout(connect=10, read=30, write=30, pool=10)
    ) as client:
        return await client.get(
            f"{GRAPH_URL}{path}",
            params={
                "$select": "id,name,size,file,folder,childCount",
                # shortcut: no @odata.nextLink paging; 200 children is enough for a demo.
                "$top": "200",
            },
            headers={"Authorization": f"Bearer {access_token}"},
        )


async def list_items(
    db: AsyncSession,
    connection: CloudConnection,
    item_id: str | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[dict]:
    """One folder level, mapped to what the browser modal renders."""
    access = await access_token_for(db, connection, transport=transport)
    response = await _children(access, item_id, transport)
    if response.status_code == 401:
        access = await access_token_for(db, connection, transport=transport)
        response = await _children(access, item_id, transport)
    if response.status_code != 200:
        raise OneDriveAuthError(f"Graph answered {response.status_code}")

    items = []
    for entry in response.json().get("value", []):
        if "file" in entry:
            items.append(
                {
                    "id": entry["id"],
                    "name": entry.get("name"),
                    "size": entry.get("size"),
                    "mime_type": entry["file"].get("mimeType"),
                    "is_folder": False,
                    "child_count": None,
                }
            )
        elif "folder" in entry:
            items.append(
                {
                    "id": entry["id"],
                    "name": entry.get("name"),
                    "size": None,
                    "mime_type": None,
                    "is_folder": True,
                    "child_count": entry["folder"].get("childCount"),
                }
            )
    return items


def _mapping(entry: dict) -> dict:
    is_folder = "folder" in entry
    return {
        "id": entry["id"],
        "name": entry.get("name"),
        "size": None if is_folder else entry.get("size"),
        "mime_type": None if is_folder else (entry.get("file") or {}).get("mimeType"),
        "is_folder": is_folder,
    }


async def get_item_metadata(
    access_token: str,
    item_id: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """Provider metadata is the authority for the gates; the client never supplies it."""
    async with httpx.AsyncClient(
        transport=transport, timeout=httpx.Timeout(connect=10, read=30, write=30, pool=10)
    ) as client:
        response = await client.get(
            f"{GRAPH_URL}/me/drive/items/{quote(item_id, safe='')}",
            params={"$select": "id,name,size,file,folder"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if response.status_code != 200:
        raise OneDriveAuthError(f"Graph answered {response.status_code}")
    return _mapping(response.json())


async def download_item(
    access_token: str,
    item_id: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
):
    """Yield the file in 1 MiB chunks. The caller enforces the upload ceiling."""
    url = f"{GRAPH_URL}/me/drive/items/{quote(item_id, safe='')}/content"
    async with httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10),
        follow_redirects=True,
    ) as client:
        async with client.stream(
            "GET", url, headers={"Authorization": f"Bearer {access_token}"}
        ) as response:
            if response.status_code != 200:
                raise OneDriveAuthError(f"Graph answered {response.status_code}")
            async for chunk in response.aiter_bytes(1024 * 1024):
                yield chunk
