"""Folders: the flat library tree and the deliberately hard delete."""

import pytest

from app.models.knowledge import DOCUMENT_STATUS_STORED, Document
from app.services.storage.filesystem import FilesystemStorage
from app.services.storage import build_storage_key


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


async def upload(client, headers, workspace_id, folder_id=None, name="notes.txt"):
    data = {"folder_id": folder_id} if folder_id else {}
    response = await client.post(
        _url(workspace_id, "/documents"),
        files={"file": (name, b"hello library", "text/plain")},
        data=data,
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_and_list_a_folder(client, auth_headers, test_workspace):
    folder = await create_folder(client, auth_headers, test_workspace.id)

    listed = await client.get(_url(test_workspace.id, "/folders"), headers=auth_headers)

    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["folders"][0]["id"] == folder["id"]
    assert body["folders"][0]["file_count"] == 0


async def test_duplicate_folder_names_are_allowed(client, auth_headers, test_workspace):
    await create_folder(client, auth_headers, test_workspace.id, "Drafts")
    response = await client.post(
        _url(test_workspace.id, "/folders"), json={"name": "Drafts"}, headers=auth_headers
    )

    assert response.status_code == 201, response.text


async def test_a_name_is_trimmed_and_an_empty_or_long_name_is_refused(
    client, auth_headers, test_workspace
):
    created = await create_folder(client, auth_headers, test_workspace.id, "  Spacey  ")
    assert created["name"] == "Spacey"

    empty = await client.post(
        _url(test_workspace.id, "/folders"), json={"name": "   "}, headers=auth_headers
    )
    long = await client.post(
        _url(test_workspace.id, "/folders"), json={"name": "x" * 256}, headers=auth_headers
    )

    assert empty.status_code == 400, empty.text
    assert long.status_code == 400, long.text


async def test_rename_a_folder(client, auth_headers, test_workspace):
    folder = await create_folder(client, auth_headers, test_workspace.id)

    response = await client.patch(
        _url(test_workspace.id, f"/folders/{folder['id']}"),
        json={"name": "Renamed"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Renamed"


async def test_an_empty_folder_deletes_with_one_request(
    client, auth_headers, test_workspace
):
    folder = await create_folder(client, auth_headers, test_workspace.id)

    response = await client.delete(
        _url(test_workspace.id, f"/folders/{folder['id']}"), headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert (await client.get(_url(test_workspace.id, "/folders"), headers=auth_headers)).json()[
        "total"
    ] == 0


async def test_a_non_empty_folder_is_refused_without_force(
    client, auth_headers, test_workspace, storage_root
):
    folder = await create_folder(client, auth_headers, test_workspace.id)
    document = await upload(client, auth_headers, test_workspace.id, folder["id"])

    response = await client.delete(
        _url(test_workspace.id, f"/folders/{folder['id']}"), headers=auth_headers
    )

    assert response.status_code == 409, response.text
    assert "1 file" in response.json()["detail"]
    # Nothing moved: the file is still in the folder and its bytes still exist.
    listed = await client.get(_url(test_workspace.id, "/documents"), headers=auth_headers)
    assert listed.json()["documents"][0]["id"] == document["id"]
    assert await FilesystemStorage(storage_root).exists(
        build_storage_key(test_workspace.id, document["id"])
    )


async def test_force_delete_requires_the_exact_name(
    client, auth_headers, test_workspace, storage_root
):
    folder = await create_folder(client, auth_headers, test_workspace.id)
    await upload(client, auth_headers, test_workspace.id, folder["id"])

    wrong = await client.request(
        "DELETE",
        _url(test_workspace.id, f"/folders/{folder['id']}?force=true"),
        json={"confirm_name": "wrong"},
        headers=auth_headers,
    )

    assert wrong.status_code == 400, wrong.text
    assert (await client.get(_url(test_workspace.id, "/folders"), headers=auth_headers)).json()[
        "total"
    ] == 1


async def test_force_delete_with_the_right_name_removes_rows_and_bytes(
    client, auth_headers, test_workspace, storage_root, db_session
):
    folder = await create_folder(client, auth_headers, test_workspace.id)
    document = await upload(client, auth_headers, test_workspace.id, folder["id"])
    key = build_storage_key(test_workspace.id, document["id"])

    response = await client.request(
        "DELETE",
        _url(test_workspace.id, f"/folders/{folder['id']}?force=true"),
        json={"confirm_name": "Handbook"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert await db_session.get(Document, document["id"]) is None
    assert await FilesystemStorage(storage_root).exists(key) is False


async def test_an_attached_file_blocks_even_a_forced_folder_delete(
    client, auth_headers, test_workspace, storage_root, db_session
):
    from app.models.agent import Agent, AgentDocument

    folder = await create_folder(client, auth_headers, test_workspace.id)
    document = await upload(client, auth_headers, test_workspace.id, folder["id"])
    agent = Agent(
        workspace_id=test_workspace.id,
        name="Reader",
        system_prompt="Read.",
        params={},
    )
    db_session.add(agent)
    await db_session.commit()
    db_session.add(
        AgentDocument(
            agent_id=agent.id, document_id=document["id"], source_folder_id=folder["id"]
        )
    )
    await db_session.commit()

    response = await client.request(
        "DELETE",
        _url(test_workspace.id, f"/folders/{folder['id']}?force=true"),
        json={"confirm_name": "Handbook"},
        headers=auth_headers,
    )

    assert response.status_code == 409, response.text
    assert "attached" in response.json()["detail"]
    assert await db_session.get(Document, document["id"]) is not None


async def test_another_workspaces_folder_is_not_found(
    client, auth_headers, test_workspace, db_session, test_user
):
    from app.models.workspace import Workspace

    other = Workspace(name="Other", owner_id=test_user.id)
    db_session.add(other)
    await db_session.commit()

    response = await client.patch(
        _url(test_workspace.id, f"/folders/{other.id}"),
        json={"name": "Nope"},
        headers=auth_headers,
    )

    assert response.status_code == 404, response.text
