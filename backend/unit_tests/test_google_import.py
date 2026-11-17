"""Importing a Google-picked file: Drive's metadata gates, then the shared service."""

import logging
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.models.knowledge import Document
from app.services import document_import
from app.services import google_drive
from app.services.storage.filesystem import FilesystemStorage

MIB = 1024 * 1024
DOC = "application/vnd.google-apps.document"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def storage(tmp_path, monkeypatch):
    backend = FilesystemStorage(tmp_path)
    monkeypatch.setattr(document_import, "get_storage", lambda: backend)
    return backend


def fake_drive(monkeypatch, meta, chunks=(b"file-bytes",)):
    calls = {"downloads": 0}

    async def get_file_metadata(*_args, **_kwargs):
        return meta

    async def download(*_args, **_kwargs):
        calls["downloads"] += 1
        return b"".join(chunks)

    monkeypatch.setattr(google_drive, "get_file_metadata", get_file_metadata)
    monkeypatch.setattr(google_drive, "download", download)
    return calls


def metadata(name="Plan", mime=DOC, size=None):
    return {"id": "file-1", "name": name, "mime_type": mime, "size": size}


def url(workspace_id):
    return f"/api/workspaces/{workspace_id}/imports/google"


@pytest.mark.asyncio
async def test_importing_a_picked_file_creates_a_document(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    fake_drive(monkeypatch, metadata(mime="application/pdf"), [b"%PDF-1.4"])

    response = await client.post(
        url(test_workspace.id),
        json={"file_id": "file-1", "access_token": "token"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    body = response.json()
    document = await db_session.get(Document, body["document_id"])
    assert document.source_provider == "google"
    assert document.source_id == "file-1"
    assert await storage.download_file(document.file_url) == b"%PDF-1.4"


@pytest.mark.asyncio
async def test_importing_the_same_file_twice_returns_the_first(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    fake_drive(monkeypatch, metadata(mime="application/pdf"), [b"%PDF-1.4"])

    first = await client.post(
        url(test_workspace.id),
        json={"file_id": "file-1", "access_token": "token"},
        headers=auth_headers,
    )
    second = await client.post(
        url(test_workspace.id),
        json={"file_id": "file-1", "access_token": "token"},
        headers=auth_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    count = await db_session.scalar(select(func.count()).select_from(Document))
    assert count == 1


@pytest.mark.asyncio
async def test_the_exported_mime_type_is_what_gets_stored(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    fake_drive(monkeypatch, metadata(name="Plan", mime=DOC), [b"docx-bytes"])

    response = await client.post(
        url(test_workspace.id),
        json={"file_id": "file-1", "access_token": "token"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    document = await db_session.get(Document, response.json()["document_id"])
    assert document.mime_type == DOCX
    assert document.filename == "Plan.docx"


@pytest.mark.asyncio
async def test_a_client_claimed_mime_cannot_bypass_the_gate(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    calls = fake_drive(
        monkeypatch,
        metadata(mime="application/vnd.google-apps.drawing"),
    )

    response = await client.post(
        url(test_workspace.id),
        json={"file_id": "file-1", "access_token": "token", "mime_type": "text/plain"},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert calls["downloads"] == 0


@pytest.mark.asyncio
async def test_a_file_over_the_ceiling_is_413_before_download(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    calls = fake_drive(monkeypatch, metadata(size=95 * MIB + 1))

    response = await client.post(
        url(test_workspace.id),
        json={"file_id": "file-1", "access_token": "token"},
        headers=auth_headers,
    )

    assert response.status_code == 413
    assert calls["downloads"] == 0


@pytest.mark.asyncio
async def test_an_expired_token_is_409_with_a_pick_again_message(
    client, auth_headers, db_session, test_user, test_workspace, monkeypatch
):
    async def expired(*_args, **_kwargs):
        raise google_drive.GoogleDriveAuthError(
            "Your Google session expired — pick the files again"
        )

    monkeypatch.setattr(google_drive, "get_file_metadata", expired)

    response = await client.post(
        url(test_workspace.id),
        json={"file_id": "file-1", "access_token": "token"},
        headers=auth_headers,
    )

    assert response.status_code == 409
    assert "pick the files again" in response.json()["detail"]


@pytest.mark.asyncio
async def test_a_missing_access_token_is_422(
    client, auth_headers, test_workspace
):
    response = await client.post(
        url(test_workspace.id),
        json={"file_id": "file-1"},
        headers=auth_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_the_access_token_is_not_logged(
    client, auth_headers, db_session, test_user, test_workspace, storage, monkeypatch
):
    from app.logging import logger as app_logger

    fake_drive(monkeypatch, metadata(mime="application/pdf"), [b"%PDF-1.4"])
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = Capture()
    app_logger.addHandler(handler)
    try:
        await client.post(
            url(test_workspace.id),
            json={"file_id": "file-1", "access_token": "secret-token-fragment"},
            headers=auth_headers,
        )
    finally:
        app_logger.removeHandler(handler)

    assert all("secret-token-fragment" not in message for message in records)
