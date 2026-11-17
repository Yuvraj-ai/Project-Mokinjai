"""The one import path both providers use: gate, store bytes, insert one row."""

from types import SimpleNamespace

import pytest

from app.models.knowledge import DOCUMENT_STATUS_STORED, Document
from app.services import document_import
from app.services.storage.filesystem import FilesystemStorage
from app.utils.errors import BadRequestException, PayloadTooLargeException

PNG_LIKE = "application/pdf"


@pytest.fixture
def storage(tmp_path, monkeypatch):
    backend = FilesystemStorage(tmp_path)
    monkeypatch.setattr(document_import, "get_storage", lambda: backend)
    return backend


async def import_file(db, workspace_id, user_id, *, storage=None, provider="onedrive",
                      source_id="item-1", filename="report.pdf", mime=PNG_LIKE,
                      data=b"%PDF-1.4 hello"):
    return await document_import.import_document(
        db,
        workspace_id=workspace_id,
        user_id=user_id,
        provider=provider,
        source_id=source_id,
        filename=filename,
        declared_content_type=mime,
        data=data,
    )


@pytest.mark.asyncio
async def test_a_new_source_creates_a_stored_document(
    db_session, test_workspace, test_user, storage
):
    document, created = await import_file(
        db_session, test_workspace.id, test_user.id
    )

    assert created is True
    assert document.status == DOCUMENT_STATUS_STORED
    assert document.content is None
    assert await storage.download_file(document.file_url) == b"%PDF-1.4 hello"


@pytest.mark.asyncio
async def test_the_same_source_twice_returns_the_first_document(
    db_session, test_workspace, test_user, storage
):
    first, created = await import_file(db_session, test_workspace.id, test_user.id)
    second, duplicate_created = await import_file(
        db_session, test_workspace.id, test_user.id
    )

    assert created is True
    assert duplicate_created is False
    assert second.id == first.id


@pytest.mark.asyncio
async def test_the_same_source_in_another_workspace_creates_a_second_document(
    db_session, test_workspace, test_user, storage
):
    from app.models.workspace import Workspace

    other = Workspace(name="Other", owner_id=test_user.id)
    db_session.add(other)
    await db_session.commit()

    first, _ = await import_file(db_session, test_workspace.id, test_user.id)
    second, created = await import_file(db_session, other.id, test_user.id)

    assert created is True
    assert second.id != first.id


@pytest.mark.asyncio
async def test_a_rejected_mime_type_raises_before_storage(
    db_session, test_workspace, test_user, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        document_import, "get_storage", lambda: SimpleNamespace(upload_file=calls.append)
    )

    with pytest.raises(BadRequestException):
        await import_file(
            db_session, test_workspace.id, test_user.id, mime="application/x-msdownload"
        )

    assert calls == []


@pytest.mark.asyncio
async def test_a_file_over_the_ceiling_raises_before_storage(
    db_session, test_workspace, test_user, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        document_import, "get_storage", lambda: SimpleNamespace(upload_file=calls.append)
    )
    monkeypatch.setattr(
        "app.services.uploads.get_settings",
        lambda: SimpleNamespace(STORAGE_MAX_UPLOAD_BYTES=10),
    )

    with pytest.raises(PayloadTooLargeException):
        await import_file(
            db_session, test_workspace.id, test_user.id, data=b"x" * 11
        )

    assert calls == []


@pytest.mark.asyncio
async def test_a_failed_commit_leaves_no_object_behind(
    db_session, test_workspace, test_user, storage, monkeypatch
):
    async def explode():
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", explode)

    with pytest.raises(RuntimeError):
        await import_file(db_session, test_workspace.id, test_user.id)

    monkeypatch.undo()
    assert [p for p in storage.root.rglob("*") if p.is_file()] == []


@pytest.mark.asyncio
async def test_provenance_is_recorded(db_session, test_workspace, test_user, storage):
    document, _ = await import_file(db_session, test_workspace.id, test_user.id)

    assert document.metadata_["original_filename"] == "report.pdf"
    assert document.metadata_["uploaded_by"] == test_user.id
    assert document.metadata_["declared_content_type"] == "application/pdf"
    assert document.metadata_["storage_backend"] == storage.name
    assert document.source_provider == "onedrive"
    assert document.source_id == "item-1"
