"""Importing one OneDrive file: metadata gates, a bounded download, one row."""

import pytest
from sqlalchemy import func, select
from types import SimpleNamespace

from app.models.cloud_connection import CloudConnection
from app.models.knowledge import Document
from app.services import cloud_connections as connection_store
from app.services import document_import
from app.services import onedrive
from app.services.storage.filesystem import FilesystemStorage

MIB = 1024 * 1024


@pytest.fixture
def storage(tmp_path, monkeypatch):
    backend = FilesystemStorage(tmp_path)
    monkeypatch.setattr(document_import, "get_storage", lambda: backend)
    return backend


async def connect(db_session, user_id, token="refresh"):
    return await connection_store.save_connection(
        db_session,
        user_id=user_id,
        provider="onedrive",
        refresh_token=token,
        account_label="me@example.com",
    )


def metadata(name="report.pdf", size=11, mime="application/pdf", folder=False):
    return {
        "id": "item-1",
        "name": name,
        "size": size,
        "mime_type": None if folder else mime,
        "is_folder": folder,
    }


def fake_onedrive(monkeypatch, meta, chunks):
    calls = {"downloads": 0}

    async def access_token_for(*_args, **_kwargs):
        return "access"

    async def get_item_metadata(*_args, **_kwargs):
        return meta

    async def download_item(*_args, **_kwargs):
        calls["downloads"] += 1
        for chunk in chunks:
            yield chunk

    monkeypatch.setattr(onedrive, "access_token_for", access_token_for)
    monkeypatch.setattr(onedrive, "get_item_metadata", get_item_metadata)
    monkeypatch.setattr(onedrive, "download_item", download_item)
    return calls


def import_url(workspace_id):
    return f"/api/workspaces/{workspace_id}/imports/onedrive"


@pytest.mark.asyncio
async def test_importing_a_file_creates_a_document(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    await connect(db_session, test_user.id)
    fake_onedrive(monkeypatch, metadata(), [b"%PDF-1.4 hello"])

    response = await client.post(
        import_url(test_workspace.id),
        json={"item_id": "item-1"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["duplicate"] is False
    document = await db_session.get(Document, body["document_id"])
    assert await storage.download_file(document.file_url) == b"%PDF-1.4 hello"


@pytest.mark.asyncio
async def test_importing_it_twice_returns_the_same_document(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    await connect(db_session, test_user.id)
    fake_onedrive(monkeypatch, metadata(), [b"%PDF-1.4 hello"])

    first = await client.post(
        import_url(test_workspace.id), json={"item_id": "item-1"}, headers=auth_headers
    )
    second = await client.post(
        import_url(test_workspace.id), json={"item_id": "item-1"}, headers=auth_headers
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["document_id"] == first.json()["document_id"]
    count = await db_session.scalar(select(func.count()).select_from(Document))
    assert count == 1


@pytest.mark.asyncio
async def test_a_file_over_the_ceiling_is_413_and_nothing_is_downloaded(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    await connect(db_session, test_user.id)
    calls = fake_onedrive(
        monkeypatch,
        metadata(size=95 * MIB + 1),
        [b"should not be read"],
    )

    response = await client.post(
        import_url(test_workspace.id), json={"item_id": "item-1"}, headers=auth_headers
    )

    assert response.status_code == 413
    assert calls["downloads"] == 0


@pytest.mark.asyncio
async def test_a_disallowed_mime_type_is_400_and_nothing_is_downloaded(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    await connect(db_session, test_user.id)
    calls = fake_onedrive(
        monkeypatch,
        metadata(mime="application/x-msdownload"),
        [b"should not be read"],
    )

    response = await client.post(
        import_url(test_workspace.id), json={"item_id": "item-1"}, headers=auth_headers
    )

    assert response.status_code == 400
    assert calls["downloads"] == 0


@pytest.mark.asyncio
async def test_a_client_claimed_mime_cannot_bypass_the_gate(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    await connect(db_session, test_user.id)
    fake_onedrive(
        monkeypatch,
        metadata(mime="application/x-msdownload"),
        [b"should not be read"],
    )

    response = await client.post(
        import_url(test_workspace.id),
        json={"item_id": "item-1", "mime_type": "text/plain"},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert list(storage.root.rglob("*")) == []


@pytest.mark.asyncio
async def test_a_download_that_exceeds_the_ceiling_mid_stream_is_413(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    import app.routers.imports as imports_module

    await connect(db_session, test_user.id)
    fake_onedrive(monkeypatch, metadata(size=None), [b"x" * 11])
    monkeypatch.setattr(
        imports_module,
        "get_settings",
        lambda: SimpleNamespace(STORAGE_MAX_UPLOAD_BYTES=10),
    )

    response = await client.post(
        import_url(test_workspace.id), json={"item_id": "item-1"}, headers=auth_headers
    )

    assert response.status_code == 413
    assert list(storage.root.rglob("*")) == []


@pytest.mark.asyncio
async def test_a_user_without_a_connection_is_409(
    client, auth_headers, test_workspace
):
    response = await client.post(
        import_url(test_workspace.id), json={"item_id": "item-1"}, headers=auth_headers
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_another_users_connection_is_not_used(
    client, auth_headers, db_session, test_user, test_workspace, monkeypatch
):
    from app.models.user import User
    from app.utils.security import hash_password

    other = User(
        email="other@example.com",
        hashed_password=hash_password("testpass123"),
        name="Other",
        is_superuser=False,
    )
    db_session.add(other)
    await db_session.commit()
    await connect(db_session, other.id, token="other-refresh")

    response = await client.post(
        import_url(test_workspace.id), json={"item_id": "item-1"}, headers=auth_headers
    )

    assert response.status_code == 409
