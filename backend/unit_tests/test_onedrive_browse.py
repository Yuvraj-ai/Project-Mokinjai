"""Browsing OneDrive: Graph's children listing, mapped to the modal's item shape."""

import httpx
import pytest
from sqlalchemy import func, select

from app.models.cloud_connection import CloudConnection
from app.services import cloud_connections as connection_store
from app.services import onedrive

GRAPH_ROOT = "/v1.0/me/drive/root/children"
GRAPH_FOLDER = "/v1.0/me/drive/items/folder-1/children"


def token_or_items(items, urls):
    def handler(request):
        urls.append(str(request.url))
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "access"})
        return httpx.Response(200, json={"value": items})

    return httpx.MockTransport(handler)


async def connection_for(db_session, user_id):
    return await connection_store.save_connection(
        db_session,
        user_id=user_id,
        provider="onedrive",
        refresh_token="refresh",
        account_label="me@example.com",
    )


@pytest.mark.asyncio
async def test_the_root_lists_files_and_folders(db_session, test_user):
    urls = []
    items = [
        {
            "id": "file-1",
            "name": "report.pdf",
            "size": 1234,
            "file": {"mimeType": "application/pdf"},
        },
        {"id": "folder-1", "name": "Docs", "folder": {"childCount": 3}},
        {"id": "ignored", "name": "weird"},
    ]
    connection = await connection_for(db_session, test_user.id)

    listed = await onedrive.list_items(
        db_session, connection, transport=token_or_items(items, urls)
    )

    assert listed == [
        {
            "id": "file-1",
            "name": "report.pdf",
            "size": 1234,
            "mime_type": "application/pdf",
            "is_folder": False,
            "child_count": None,
        },
        {
            "id": "folder-1",
            "name": "Docs",
            "size": None,
            "mime_type": None,
            "is_folder": True,
            "child_count": 3,
        },
    ]
    assert any(GRAPH_ROOT in url for url in urls)


@pytest.mark.asyncio
async def test_a_subfolder_lists_its_children(db_session, test_user):
    urls = []
    connection = await connection_for(db_session, test_user.id)

    await onedrive.list_items(
        db_session, connection, item_id="folder-1", transport=token_or_items([], urls)
    )

    assert any(GRAPH_FOLDER in url for url in urls)


@pytest.mark.asyncio
async def test_a_folder_is_never_reported_as_importable(db_session, test_user):
    items = [{"id": "folder-1", "name": "Docs", "folder": {"childCount": 0}}]
    connection = await connection_for(db_session, test_user.id)

    listed = await onedrive.list_items(
        db_session, connection, transport=token_or_items(items, [])
    )

    assert listed[0]["is_folder"] is True
    assert listed[0]["mime_type"] is None


@pytest.mark.asyncio
async def test_a_missing_connection_is_409(client, auth_headers):
    response = await client.get("/api/cloud-connections/onedrive/items", headers=auth_headers)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_an_expired_refresh_token_is_409_and_the_row_is_kept(
    client, auth_headers, db_session, test_user, monkeypatch
):
    await connection_for(db_session, test_user.id)

    async def expired(*_args, **_kwargs):
        raise onedrive.OneDriveAuthError("invalid_grant")

    monkeypatch.setattr(onedrive, "list_items", expired)

    response = await client.get("/api/cloud-connections/onedrive/items", headers=auth_headers)

    assert response.status_code == 409
    assert "Reconnect OneDrive" in response.json()["detail"]
    count = await db_session.scalar(select(func.count()).select_from(CloudConnection))
    assert count == 1
