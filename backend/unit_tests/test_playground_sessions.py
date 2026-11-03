"""Playground session CRUD over HTTP (plan Task 2)."""

import pytest

from app.models.agent import Agent
from app.models.chat import ChatMessage, ChatSession


async def _make_agent(db_session, workspace_id: str, name: str = "Helper") -> Agent:
    agent = Agent(
        workspace_id=workspace_id,
        name=name,
        llm_profile_id=None,
        system_prompt="",
        params={},
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    return agent


@pytest.mark.asyncio
async def test_create_list_get_rename_delete_roundtrip(
    client, auth_headers, test_workspace, db_session
):
    agent = await _make_agent(db_session, test_workspace.id)
    base = f"/api/workspaces/{test_workspace.id}/playground"

    created = await client.post(
        base + "/sessions", json={"agent_id": agent.id}, headers=auth_headers
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["title"] == "New session"
    assert body["agent_id"] == agent.id

    listed = await client.get(base + "/sessions", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["sessions"][0]["id"] == body["id"]

    filtered = await client.get(
        base + f"/sessions?agent_id={agent.id}", headers=auth_headers
    )
    assert filtered.json()["total"] == 1

    detail = await client.get(base + f"/sessions/{body['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["messages"] == []

    renamed = await client.patch(
        base + f"/sessions/{body['id']}",
        json={"title": "Q4 revenue"},
        headers=auth_headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Q4 revenue"

    deleted = await client.delete(
        base + f"/sessions/{body['id']}", headers=auth_headers
    )
    assert deleted.status_code == 200
    gone = await client.get(base + f"/sessions/{body['id']}", headers=auth_headers)
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_viewer_reads_but_cannot_write(
    client, viewer_headers, test_workspace, db_session
):
    agent = await _make_agent(db_session, test_workspace.id)
    base = f"/api/workspaces/{test_workspace.id}/playground"

    session = ChatSession(workspace_id=test_workspace.id, agent_id=agent.id)
    db_session.add(session)
    await db_session.commit()

    assert (await client.get(base + "/sessions", headers=viewer_headers)).status_code == 200
    detail = await client.get(base + f"/sessions/{session.id}", headers=viewer_headers)
    assert detail.status_code == 200

    assert (
        await client.post(base + "/sessions", json={"agent_id": agent.id}, headers=viewer_headers)
    ).status_code == 403
    assert (
        await client.delete(base + f"/sessions/{session.id}", headers=viewer_headers)
    ).status_code == 403


@pytest.mark.asyncio
async def test_other_workspace_session_is_404(
    client, auth_headers, test_workspace, test_user, db_session
):
    # A session in a foreign workspace is invisible: 404, never a 403 leak.
    from app.models.workspace import Workspace

    agent = await _make_agent(db_session, test_workspace.id)
    other_ws = Workspace(name="Other", owner_id=test_user.id)
    db_session.add(other_ws)
    await db_session.flush()
    session = ChatSession(workspace_id=other_ws.id, agent_id=agent.id)
    db_session.add(session)
    await db_session.commit()

    base = f"/api/workspaces/{test_workspace.id}/playground"
    response = await client.get(base + f"/sessions/{session.id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_with_foreign_agent_404(client, auth_headers, test_workspace):
    base = f"/api/workspaces/{test_workspace.id}/playground"
    response = await client.post(
        base + "/sessions",
        json={"agent_id": "00000000-0000-0000-0000-00000000eeee"},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_returns_messages_in_order(
    client, auth_headers, test_workspace, db_session
):
    agent = await _make_agent(db_session, test_workspace.id)
    session = ChatSession(workspace_id=test_workspace.id, agent_id=agent.id, title="T")
    db_session.add(session)
    await db_session.flush()
    db_session.add_all(
        [
            ChatMessage(session_id=session.id, role="user", content="first"),
            ChatMessage(session_id=session.id, role="assistant", content="reply", status="completed"),
            ChatMessage(session_id=session.id, role="user", content="second"),
        ]
    )
    await db_session.commit()

    detail = await client.get(
        f"/api/workspaces/{test_workspace.id}/playground/sessions/{session.id}",
        headers=auth_headers,
    )
    assert detail.status_code == 200
    roles = [(m["role"], m["content"]) for m in detail.json()["messages"]]
    assert roles == [
        ("user", "first"),
        ("assistant", "reply"),
        ("user", "second"),
    ]
    assert detail.json()["messages"][1]["status"] == "completed"
