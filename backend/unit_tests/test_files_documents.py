"""Files: upload, filter, move, download, and the attachment delete guard."""

import pytest

from app.config import get_settings
from app.models.agent import Agent, AgentDocument
from app.models.knowledge import DOCUMENT_STATUS_STORED, Document
from app.services.storage import build_storage_key
from app.services.storage.filesystem import FilesystemStorage


def _url(workspace_id: str, suffix: str = "") -> str:
    return f"/api/workspaces/{workspace_id}/files{suffix}"


@pytest.fixture
def storage_root(tmp_path, monkeypatch):
    monkeypatch.setattr("app.routers.files.get_storage", lambda: FilesystemStorage(tmp_path))
    return tmp_path


async def create_folder(client, headers, workspace_id, name="Handbook"):
    response = await client.post(
        _url(workspace_id, "/folders"), json={"name": name}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


async def upload(
    client, headers, workspace_id, folder_id=None, name="notes.txt", body=b"hello library"
):
    data = {"folder_id": folder_id} if folder_id else {}
    response = await client.post(
        _url(workspace_id, "/documents"),
        files={"file": (name, body, "text/plain")},
        data=data,
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def attach(db_session, workspace_id, document_id, source_folder_id=None):
    agent = Agent(
        workspace_id=workspace_id, name="Reader", system_prompt="Read.", params={}
    )
    db_session.add(agent)
    await db_session.commit()
    db_session.add(
        AgentDocument(
            agent_id=agent.id,
            document_id=document_id,
            source_folder_id=source_folder_id,
        )
    )
    await db_session.commit()
    return agent


async def test_upload_to_the_root_writes_bytes_and_a_null_folder(
    client, auth_headers, test_workspace, storage_root, db_session
):
    body = await upload(client, auth_headers, test_workspace.id)

    assert body["folder_id"] is None
    assert body["filename"] == "notes.txt"
    assert body["file_size"] == len(b"hello library")
    assert body["mime_type"] == "text/plain"
    assert body["attached_agent_count"] == 0

    row = await db_session.get(Document, body["id"])
    assert row.workspace_id == test_workspace.id
    assert row.content is None
    assert row.status == DOCUMENT_STATUS_STORED
    assert await FilesystemStorage(storage_root).exists(
        build_storage_key(test_workspace.id, body["id"])
    )


async def test_upload_into_a_folder_and_an_unknown_folder_writes_nothing(
    client, auth_headers, test_workspace, storage_root
):
    folder = await create_folder(client, auth_headers, test_workspace.id)
    body = await upload(client, auth_headers, test_workspace.id, folder["id"])
    assert body["folder_id"] == folder["id"]

    before = len(list(storage_root.rglob("*")))
    response = await client.post(
        _url(test_workspace.id, "/documents"),
        files={"file": ("x.txt", b"x", "text/plain")},
        data={"folder_id": "missing"},
        headers=auth_headers,
    )

    assert response.status_code == 404, response.text
    assert len(list(storage_root.rglob("*"))) == before


async def test_upload_refuses_a_type_outside_the_whitelist(
    client, auth_headers, test_workspace, storage_root
):
    response = await client.post(
        _url(test_workspace.id, "/documents"),
        files={"file": ("a.zip", b"x", "application/zip")},
        headers=auth_headers,
    )

    assert response.status_code == 400, response.text
    assert list(storage_root.iterdir()) == []


async def test_upload_refuses_an_empty_file(client, auth_headers, test_workspace, storage_root):
    response = await client.post(
        _url(test_workspace.id, "/documents"),
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=auth_headers,
    )

    assert response.status_code == 400, response.text


async def test_the_upload_ceiling_is_95_mib():
    assert get_settings().STORAGE_MAX_UPLOAD_BYTES == 95 * 1024 * 1024


async def test_upload_refuses_a_body_over_the_configured_limit(
    client, auth_headers, test_workspace, storage_root, monkeypatch
):
    monkeypatch.setattr(get_settings(), "STORAGE_MAX_UPLOAD_BYTES", 8)

    response = await client.post(
        _url(test_workspace.id, "/documents"),
        files={"file": ("a.txt", b"more than eight bytes", "text/plain")},
        headers=auth_headers,
    )

    assert response.status_code == 413, response.text
    assert list(storage_root.iterdir()) == []


async def test_listing_filters_by_folder_root_and_name(
    client, auth_headers, test_workspace
):
    folder = await create_folder(client, auth_headers, test_workspace.id)
    filed = await upload(client, auth_headers, test_workspace.id, folder["id"], "filed.txt")
    root = await upload(client, auth_headers, test_workspace.id, None, "root.txt")

    everything = await client.get(_url(test_workspace.id, "/documents"), headers=auth_headers)
    unfiled = await client.get(
        _url(test_workspace.id, "/documents?unfiled=true"), headers=auth_headers
    )
    in_folder = await client.get(
        _url(test_workspace.id, f"/documents?folder_id={folder['id']}"), headers=auth_headers
    )
    searched = await client.get(
        _url(test_workspace.id, "/documents?q=filed"), headers=auth_headers
    )

    assert everything.json()["total"] == 2
    assert [row["id"] for row in unfiled.json()["documents"]] == [root["id"]]
    assert [row["id"] for row in in_folder.json()["documents"]] == [filed["id"]]
    assert [row["id"] for row in searched.json()["documents"]] == [filed["id"]]


async def test_a_file_moves_to_a_folder_and_back_to_the_root(
    client, auth_headers, test_workspace
):
    folder = await create_folder(client, auth_headers, test_workspace.id)
    document = await upload(client, auth_headers, test_workspace.id)

    moved = await client.patch(
        _url(test_workspace.id, "/documents"),
        json={"document_ids": [document["id"]], "folder_id": folder["id"]},
        headers=auth_headers,
    )
    assert moved.status_code == 200
    assert moved.json() == {"moved": 1}

    back = await client.patch(
        _url(test_workspace.id, "/documents"),
        json={"document_ids": [document["id"]], "folder_id": None},
        headers=auth_headers,
    )
    assert back.status_code == 200

    listed = await client.get(
        _url(test_workspace.id, "/documents?unfiled=true"), headers=auth_headers
    )
    assert listed.json()["documents"][0]["folder_id"] is None


async def test_move_refuses_an_unknown_id_and_moves_nothing(
    client, auth_headers, test_workspace
):
    folder = await create_folder(client, auth_headers, test_workspace.id)
    document = await upload(client, auth_headers, test_workspace.id)

    response = await client.patch(
        _url(test_workspace.id, "/documents"),
        json={"document_ids": [document["id"], "missing"], "folder_id": folder["id"]},
        headers=auth_headers,
    )

    assert response.status_code == 404, response.text
    listed = await client.get(
        _url(test_workspace.id, "/documents?unfiled=true"), headers=auth_headers
    )
    assert listed.json()["total"] == 1


async def test_an_attached_file_cannot_be_deleted(
    client, auth_headers, test_workspace, db_session, storage_root
):
    document = await upload(client, auth_headers, test_workspace.id)
    await attach(db_session, test_workspace.id, document["id"])

    response = await client.delete(
        _url(test_workspace.id, f"/documents/{document['id']}"), headers=auth_headers
    )

    assert response.status_code == 409, response.text
    assert "attached to 1 agent" in response.json()["detail"]
    assert await db_session.get(Document, document["id"]) is not None


async def test_an_unattached_file_deletes_its_row_and_bytes(
    client, auth_headers, test_workspace, db_session, storage_root
):
    document = await upload(client, auth_headers, test_workspace.id)
    key = build_storage_key(test_workspace.id, document["id"])

    response = await client.delete(
        _url(test_workspace.id, f"/documents/{document['id']}"), headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert await db_session.get(Document, document["id"]) is None
    assert await FilesystemStorage(storage_root).exists(key) is False


async def test_download_returns_the_bytes(
    client, auth_headers, test_workspace, storage_root
):
    document = await upload(client, auth_headers, test_workspace.id, body=b"exact bytes")

    response = await client.get(
        _url(test_workspace.id, f"/documents/{document['id']}/download"),
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.content == b"exact bytes"
    assert "notes.txt" in response.headers["content-disposition"]


async def test_a_viewer_reads_and_cannot_write(
    client, viewer_headers, auth_headers, test_workspace, storage_root
):
    document = await upload(client, auth_headers, test_workspace.id)

    read = await client.get(
        _url(test_workspace.id, "/documents"), headers=viewer_headers
    )
    write = await client.post(
        _url(test_workspace.id, "/folders"), json={"name": "Nope"}, headers=viewer_headers
    )

    assert read.status_code == 200
    assert document["id"] in [row["id"] for row in read.json()["documents"]]
    assert write.status_code == 403


async def test_another_workspaces_document_is_not_found(
    client, auth_headers, test_workspace, db_session, test_user
):
    from app.models.workspace import Workspace

    other = Workspace(name="Other", owner_id=test_user.id)
    db_session.add(other)
    await db_session.commit()
    db_session.add(
        Document(
            workspace_id=other.id,
            filename="theirs.txt",
            file_url="workspaces/other/files/x",
            status=DOCUMENT_STATUS_STORED,
        )
    )
    await db_session.commit()

    response = await client.get(
        _url(test_workspace.id, "/documents?q=theirs"), headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
