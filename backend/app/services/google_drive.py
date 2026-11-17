"""Drive bytes for files the user picked in Google's own dialog.

The Picker's `drive.file` token is short-lived and passed in the request. Nothing is
stored here, and every gate uses metadata fetched by id rather than anything the
browser claimed.
"""

from urllib.parse import quote

import httpx

from app.config import get_settings
from app.utils.errors import BadRequestException, PayloadTooLargeException

DRIVE_URL = "https://www.googleapis.com/drive/v3"

GOOGLE_EXPORT_TYPES = {
    "application/vnd.google-apps.document":
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.spreadsheet":
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.presentation": "application/pdf",
}

EXPORT_EXTENSIONS = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/pdf": ".pdf",
}


class GoogleDriveAuthError(Exception):
    """The token, permission or quota refused the request. The user must pick again."""


def export_mime(mime_type: str) -> str | None:
    return GOOGLE_EXPORT_TYPES.get(mime_type)


def export_extension(mime_type: str) -> str | None:
    return EXPORT_EXTENSIONS.get(export_mime(mime_type) or "")


def _unauthorized() -> GoogleDriveAuthError:
    return GoogleDriveAuthError("Your Google session expired — pick the files again")


def _forbidden(response: httpx.Response) -> GoogleDriveAuthError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    reasons = {
        error.get("reason")
        for error in body.get("error", {}).get("errors", [])
        if isinstance(error, dict)
    }
    if "insufficientFilePermissions" in reasons:
        return GoogleDriveAuthError("You do not have permission to read this file.")
    if "quotaExceeded" in reasons:
        return GoogleDriveAuthError("Google Drive quota exceeded; try again later.")
    return GoogleDriveAuthError("Google Drive refused the request.")


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code == 401:
        raise _unauthorized()
    if response.status_code == 403:
        raise _forbidden(response)
    if response.status_code != 200:
        raise GoogleDriveAuthError(f"Google Drive answered {response.status_code}.")


async def get_file_metadata(
    file_id: str,
    access_token: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    async with httpx.AsyncClient(
        transport=transport, timeout=httpx.Timeout(connect=10, read=30, write=30, pool=10)
    ) as client:
        response = await client.get(
            f"{DRIVE_URL}/files/{quote(file_id, safe='')}",
            params={"fields": "id,name,mimeType,size"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
    _raise_for_status(response)
    payload = response.json()
    size = payload.get("size")
    return {
        "id": payload.get("id", file_id),
        "name": payload.get("name"),
        "mime_type": payload.get("mimeType"),
        "size": int(size) if size not in (None, "") else None,
    }


async def download(
    file_id: str,
    mime_type: str,
    access_token: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> bytes:
    """Export a Google-native file, or download a binary one, bounded while reading."""
    target = export_mime(mime_type)
    if target is None and mime_type.startswith("application/vnd.google-apps."):
        raise BadRequestException(f"Cannot import Google type {mime_type}")
    path = f"/files/{quote(file_id, safe='')}"
    params = {"mimeType": target} if target else {"alt": "media"}

    limit = get_settings().STORAGE_MAX_UPLOAD_BYTES
    data = bytearray()
    async with httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(connect=10, read=120, write=30, pool=10),
        follow_redirects=True,
    ) as client:
        async with client.stream(
            "GET",
            f"{DRIVE_URL}{path}" + ("/export" if target else ""),
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        ) as response:
            if response.status_code != 200:
                await response.aread()
                _raise_for_status(response)
            async for chunk in response.aiter_bytes(1024 * 1024):
                if len(data) + len(chunk) > limit:
                    raise PayloadTooLargeException(
                        f"File exceeds the {limit} byte limit"
                    )
                data.extend(chunk)
    return bytes(data)
