"""Knowledge Base documents: the type narrowing, the document contract, and the seams.

What this file does not test is text extraction or retrieval — neither exists, and
neither is this feature's. `test_the_documents_table_carries_no_vector_machinery` is the
guard that keeps that true while the vector design is still pending.
"""

import pytest
from sqlalchemy import select, text

from app.config import get_settings
from app.models.knowledge import DOCUMENT_STATUS_STORED, Document
from app.models.workspace import Workspace, WorkspaceMember
from app.routers.knowledge import _persist_document
from app.services.storage import build_storage_key
from app.services.storage.filesystem import FilesystemStorage


def _kb_body(**overrides):
    payload = {"name": "Handbook", "description": "Company docs"}
    payload.update(overrides)
    return payload


def _kb_url(workspace_id: str) -> str:
    return f"/api/workspaces/{workspace_id}/knowledge-bases"


async def test_creating_a_document_knowledge_base_succeeds(
    client, auth_headers, test_workspace
):
    response = await client.post(
        _kb_url(test_workspace.id), json=_kb_body(type="document"), headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["type"] == "document"


async def test_the_default_type_is_document(client, auth_headers, test_workspace):
    response = await client.post(
        _kb_url(test_workspace.id), json=_kb_body(), headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["type"] == "document"


@pytest.mark.parametrize("kb_type", ["url", "api", "anything"])
async def test_an_unsupported_type_is_refused(
    client, auth_headers, test_workspace, kb_type
):
    """`url` and `api` are refused, not accepted-and-ignored.

    Neither has a design: a url knowledge base implies fetching and crawling, and an api
    knowledge base is undefined altogether. Storing a row nothing can act on is a lie the
    UI would have to repeat.
    """
    response = await client.post(
        _kb_url(test_workspace.id), json=_kb_body(type=kb_type), headers=auth_headers
    )

    assert response.status_code == 400, response.text
    assert kb_type in response.json()["detail"]


async def test_the_documents_table_carries_no_vector_machinery(db_session):
    """The deferral, pinned at the table level.

    `test_schema_types.py` pins `vector_ids` to `text`. This pins the whole column set, so
    an embedding column, a dimension constant or an `ARRAY` cannot arrive before the
    vector design lands and the `vector_ids` question is answered.
    """
    rows = await db_session.execute(
        text(
            "select column_name from information_schema.columns "
            "where table_schema = 'public' and table_name = 'documents'"
        )
    )

    assert {row[0] for row in rows} == {
        "id",
        "knowledge_base_id",
        "filename",
        "file_url",
        "file_size",
        "mime_type",
        "content",
        "metadata",
        "vector_ids",
        "status",
        "created_at",
        "updated_at",
    }


def test_the_status_vocabulary_is_the_decided_set():
    from app.models.knowledge import (
        DOCUMENT_STATUS_FAILED,
        DOCUMENT_STATUS_INDEXED,
        DOCUMENT_STATUS_STORED,
        DOCUMENT_STATUSES,
    )

    assert DOCUMENT_STATUSES == ("stored", "indexed", "failed")
    assert DOCUMENT_STATUS_STORED == "stored"
    assert DOCUMENT_STATUS_INDEXED == "indexed"
    assert DOCUMENT_STATUS_FAILED == "failed"


@pytest.fixture
def storage_root(tmp_path, monkeypatch):
    """The real filesystem backend, writing into a directory this test owns.

    Monkeypatching the router's `get_storage` replaces the outbound dependency, not the
    code under test — the same shape as test_llm_profiles.py's monkeypatch of the probe.
    """
    monkeypatch.setattr("app.routers.knowledge.get_storage", lambda: FilesystemStorage(tmp_path))
    return tmp_path


async def _create_kb(client, auth_headers, test_workspace, name="Handbook"):
    response = await client.post(
        _kb_url(test_workspace.id), json={"name": name}, headers=auth_headers
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _documents_url(workspace_id: str, kb_id: str) -> str:
    return f"{_kb_url(workspace_id)}/{kb_id}/documents"


def _upload_spec(name: str = "notes.txt", content_type: str = "text/plain"):
    return {"file": (name, b"hello knowledge base", content_type)}


async def test_upload_writes_the_bytes_and_the_row(
    client, auth_headers, test_workspace, storage_root
):
    kb_id = await _create_kb(client, auth_headers, test_workspace)

    response = await client.post(
        _documents_url(test_workspace.id, kb_id), files=_upload_spec(), headers=auth_headers
    )

    assert response.status_code == 201, response.text
    body = response.json()
    document_id = body["id"]

    assert body["knowledge_base_id"] == kb_id
    assert body["filename"] == "notes.txt"
    assert body["file_size"] == len(b"hello knowledge base")
    assert body["mime_type"] == "text/plain"
    assert body["status"] == "stored"
    assert body["metadata"]["original_filename"] == "notes.txt"
    assert body["metadata"]["declared_content_type"] == "text/plain"
    assert body["metadata"]["storage_backend"] == "filesystem"
    assert body["metadata"]["uploaded_by"]
    assert "file_url" not in body, "the storage key is internal"
    assert "vector_ids" not in body

    # The bytes are on disk at exactly the key the design settles.
    key = build_storage_key(test_workspace.id, kb_id, document_id)
    stored = FilesystemStorage(storage_root)
    assert await stored.exists(key) is True
    assert await stored.download_file(key) == b"hello knowledge base"


async def test_upload_stores_the_declared_type_normalised_and_keeps_the_raw_claim(
    client, auth_headers, test_workspace, storage_root
):
    """Browsers send `text/plain; charset=utf-8`, and the raw claim is kept separately."""
    kb_id = await _create_kb(client, auth_headers, test_workspace)

    response = await client.post(
        _documents_url(test_workspace.id, kb_id),
        files=_upload_spec(content_type="text/plain; charset=utf-8"),
        headers=auth_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["mime_type"] == "text/plain"
    assert response.json()["metadata"]["declared_content_type"] == "text/plain; charset=utf-8"


async def test_upload_keeps_a_document_out_of_the_content_and_status_seams(
    client, auth_headers, test_workspace, storage_root, db_session
):
    """`content` stays NULL and `status` stays `stored`: extraction is Phase 2's."""
    kb_id = await _create_kb(client, auth_headers, test_workspace)

    response = await client.post(
        _documents_url(test_workspace.id, kb_id), files=_upload_spec(), headers=auth_headers
    )

    row = (
        await db_session.execute(select(Document).where(Document.id == response.json()["id"]))
    ).scalar_one()
    assert row.content is None
    assert row.status == DOCUMENT_STATUS_STORED
    assert row.vector_ids is None


@pytest.mark.parametrize("content_type", ["application/zip", "image/png", ""])
async def test_upload_refuses_a_type_outside_the_whitelist(
    client, auth_headers, test_workspace, storage_root, content_type
):
    kb_id = await _create_kb(client, auth_headers, test_workspace)

    response = await client.post(
        _documents_url(test_workspace.id, kb_id),
        files=_upload_spec(content_type=content_type),
        headers=auth_headers,
    )

    assert response.status_code == 400, response.text
    assert list(storage_root.iterdir()) == [], "nothing may be written for a refused upload"


async def test_upload_refuses_an_empty_file(
    client, auth_headers, test_workspace, storage_root
):
    kb_id = await _create_kb(client, auth_headers, test_workspace)

    response = await client.post(
        _documents_url(test_workspace.id, kb_id),
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=auth_headers,
    )

    assert response.status_code == 400, response.text
    assert list(storage_root.iterdir()) == []


async def test_upload_refuses_a_file_over_the_limit(
    client, auth_headers, test_workspace, storage_root, monkeypatch
):
    monkeypatch.setattr(get_settings(), "STORAGE_MAX_UPLOAD_BYTES", 8)
    kb_id = await _create_kb(client, auth_headers, test_workspace)

    response = await client.post(
        _documents_url(test_workspace.id, kb_id), files=_upload_spec(), headers=auth_headers
    )

    assert response.status_code == 413, response.text
    assert list(storage_root.iterdir()) == [], "an over-limit body must not reach storage"


async def test_upload_into_another_workspaces_knowledge_base_is_not_found(
    client, auth_headers, test_workspace, test_user, storage_root, db_session
):
    other = Workspace(name="Other Workspace", owner_id=test_user.id)
    db_session.add(other)
    await db_session.commit()
    db_session.add(WorkspaceMember(workspace_id=other.id, user_id=test_user.id, role="owner"))
    await db_session.commit()
    kb_id = await _create_kb(client, auth_headers, test_workspace)

    response = await client.post(
        _documents_url(other.id, kb_id), files=_upload_spec(), headers=auth_headers
    )

    assert response.status_code == 404, response.text


async def test_upload_requires_editor(
    client, auth_headers, viewer_headers, test_workspace, storage_root
):
    """A viewer is a member of this workspace, so the refusal must be a permission.

    The other half of the split — that the same viewer may still read — is Task 6's
    `test_download_is_a_viewer_operation`, which cannot run before download exists.
    """
    kb_id = await _create_kb(client, auth_headers, test_workspace)

    response = await client.post(
        _documents_url(test_workspace.id, kb_id), files=_upload_spec(), headers=viewer_headers
    )

    assert response.status_code == 403, response.text


class _CommitFails:
    """A session whose commit always fails, for the compensating delete."""

    def __init__(self):
        self.added = []

    def add(self, row):
        self.added.append(row)

    async def commit(self):
        raise RuntimeError("database exploded")


async def test_a_failed_commit_removes_the_written_object(storage_root):
    """The one failure path a reader would otherwise take on faith.

    Bytes are written before the row, so this is the failure ordering can produce: the
    half that succeeded is undone rather than left pointing at nothing.
    """
    storage = FilesystemStorage(storage_root)
    key = build_storage_key("ws", "kb", "doc")
    await storage.upload_file(key, b"bytes", content_type="text/plain")
    document = Document(
        id="doc", knowledge_base_id="kb", file_url=key, status=DOCUMENT_STATUS_STORED
    )

    with pytest.raises(RuntimeError):
        await _persist_document(_CommitFails(), storage, document)

    assert await storage.exists(key) is False, "the half that succeeded must be undone"


async def _upload(client, auth_headers, workspace_id, kb_id, name="notes.txt", body=b"hello"):
    response = await client.post(
        _documents_url(workspace_id, kb_id),
        files={"file": (name, body, "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _stored_files(storage_root):
    """Every file under the storage root, as paths, so a leak is visible."""
    return sorted(path for path in storage_root.rglob("*") if path.is_file())


async def test_listing_returns_the_documents(client, auth_headers, test_workspace, storage_root):
    kb_id = await _create_kb(client, auth_headers, test_workspace)
    first = await _upload(client, auth_headers, test_workspace.id, kb_id, name="a.txt")
    second = await _upload(client, auth_headers, test_workspace.id, kb_id, name="b.txt")

    response = await client.get(
        _documents_url(test_workspace.id, kb_id), headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    assert {d["id"] for d in response.json()["documents"]} == {first["id"], second["id"]}


async def test_getting_one_document_returns_its_metadata(
    client, auth_headers, test_workspace, storage_root
):
    kb_id = await _create_kb(client, auth_headers, test_workspace)
    created = await _upload(client, auth_headers, test_workspace.id, kb_id)

    response = await client.get(
        f"{_documents_url(test_workspace.id, kb_id)}/{created['id']}", headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["filename"] == "notes.txt"
    assert response.json()["status"] == "stored"


async def test_download_returns_the_bytes_and_replays_the_stored_type(
    client, auth_headers, test_workspace, storage_root
):
    kb_id = await _create_kb(client, auth_headers, test_workspace)
    created = await _upload(client, auth_headers, test_workspace.id, kb_id, body=b"exact bytes")

    response = await client.get(
        f"{_documents_url(test_workspace.id, kb_id)}/{created['id']}/download",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.content == b"exact bytes"
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["content-disposition"] == 'attachment; filename="notes.txt"'


async def test_download_keeps_only_the_basename_of_a_client_filename(
    client, auth_headers, test_workspace, storage_root
):
    """The client's path is a label, and the storage key is untouched by it."""
    kb_id = await _create_kb(client, auth_headers, test_workspace)
    created = await _upload(
        client, auth_headers, test_workspace.id, kb_id, name="../evil.txt"
    )

    assert created["filename"] == "evil.txt"
    assert created["metadata"]["original_filename"] == "evil.txt"

    response = await client.get(
        f"{_documents_url(test_workspace.id, kb_id)}/{created['id']}/download",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"] == 'attachment; filename="evil.txt"'


def test_the_header_sanitiser_removes_quotes_and_control_characters():
    """A pure unit, because CR and LF cannot be sent reliably inside a multipart filename.

    The endpoint test above covers the basename rule end to end; this covers the
    characters that would let a filename terminate its own header parameter.
    """
    from app.routers.knowledge import _header_safe_filename

    assert _header_safe_filename('a\r\nb"c;d.txt') == "a__b_c_d.txt"
    assert _header_safe_filename('"') == "download"


async def test_download_is_a_viewer_operation(
    client, auth_headers, viewer_headers, test_workspace, storage_root
):
    kb_id = await _create_kb(client, auth_headers, test_workspace)
    created = await _upload(client, auth_headers, test_workspace.id, kb_id)

    response = await client.get(
        f"{_documents_url(test_workspace.id, kb_id)}/{created['id']}/download",
        headers=viewer_headers,
    )

    assert response.status_code == 200, response.text


async def test_deleting_a_document_removes_the_row_and_the_object(
    client, auth_headers, test_workspace, storage_root
):
    kb_id = await _create_kb(client, auth_headers, test_workspace)
    created = await _upload(client, auth_headers, test_workspace.id, kb_id)
    assert len(_stored_files(storage_root)) == 1

    response = await client.delete(
        f"{_documents_url(test_workspace.id, kb_id)}/{created['id']}", headers=auth_headers
    )
    assert response.status_code == 200, response.text

    assert _stored_files(storage_root) == []
    gone = await client.get(
        f"{_documents_url(test_workspace.id, kb_id)}/{created['id']}", headers=auth_headers
    )
    assert gone.status_code == 404, gone.text


async def test_deleting_a_knowledge_base_removes_its_objects(
    client, auth_headers, test_workspace, storage_root
):
    """The endpoint that used to strand every object it owned."""
    kb_id = await _create_kb(client, auth_headers, test_workspace)
    await _upload(client, auth_headers, test_workspace.id, kb_id, name="a.txt")
    await _upload(client, auth_headers, test_workspace.id, kb_id, name="b.txt")
    assert len(_stored_files(storage_root)) == 2

    response = await client.delete(f"{_kb_url(test_workspace.id)}/{kb_id}", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert _stored_files(storage_root) == [], "the knowledge base's objects must go with it"


async def test_a_document_is_not_readable_through_another_knowledge_base(
    client, auth_headers, test_workspace, storage_root
):
    first_kb = await _create_kb(client, auth_headers, test_workspace, name="First")
    second_kb = await _create_kb(client, auth_headers, test_workspace, name="Second")
    created = await _upload(client, auth_headers, test_workspace.id, first_kb)

    for suffix in ("", "/download"):
        response = await client.get(
            f"{_documents_url(test_workspace.id, second_kb)}/{created['id']}{suffix}",
            headers=auth_headers,
        )
        assert response.status_code == 404, f"{suffix or '/'} leaked across knowledge bases"

