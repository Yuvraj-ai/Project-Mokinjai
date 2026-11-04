"""The public /v1 surface (plan Task 3): auth isolation, chat contract,
session scoping, streaming."""

import json

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.config import get_settings
from app.models.agent import Agent
from app.models.chat import ChatMessage, ChatSession
from app.models.execution import Execution
from app.services.api_keys import create_key

from unit_tests.test_playground_chat import FakeGraphV2, make_profile


@pytest.fixture
def encryption_key():
    settings = get_settings()
    previous = getattr(settings, "LLM_ENCRYPTION_KEY", "")
    settings.LLM_ENCRYPTION_KEY = Fernet.generate_key().decode()
    yield settings.LLM_ENCRYPTION_KEY
    settings.LLM_ENCRYPTION_KEY = previous


def auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


async def _key_and_agent(db_session, test_workspace, test_user):
    key, plaintext = await create_key(
        db_session, workspace_id=test_workspace.id, user_id=test_user.id, name="Public"
    )
    profile = make_profile(test_workspace.id)
    db_session.add(profile)
    await db_session.flush()
    agent = Agent(
        workspace_id=test_workspace.id,
        name="Public Agent",
        llm_profile_id=profile.id,
        system_prompt="Be brief.",
        params={},
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(key)
    await db_session.refresh(agent)
    return key, plaintext, agent


def _install(monkeypatch, session_factory):
    monkeypatch.setattr("app.services.agent_runtime.async_session", session_factory)
    monkeypatch.setattr(
        "app.services.agent_runtime.build_graph", lambda *a, **k: FakeGraphV2()
    )


class TestAuthIsolation:
    @pytest.mark.asyncio
    async def test_missing_unknown_and_malformed_keys_are_401(
        self, client, test_workspace, test_user, db_session
    ):
        _, plaintext, _ = await _key_and_agent(db_session, test_workspace, test_user)
        url = "/v1/chat"
        assert (
            await client.post(url, json={"agent_id": "x", "message": "hi"})
        ).status_code == 401
        bad = await client.post(
            url, json={"agent_id": "x", "message": "hi"}, headers={"Authorization": "Bearer nope"}
        )
        assert bad.status_code == 401
        assert bad.json()["error"]["code"] == "invalid_api_key"
        assert bad.json()["error"]["type"] == "authentication_error"
        assert "request_id" in bad.json()["error"]

    @pytest.mark.asyncio
    async def test_session_token_cannot_open_v1_and_key_cannot_open_api(
        self, client, auth_headers, test_workspace, test_user, db_session
    ):
        # A human session token on /v1 → 401.
        human = await client.post(
            "/v1/chat", json={"agent_id": "x", "message": "hi"}, headers=auth_headers
        )
        assert human.status_code == 401

        # An agent key on an /api dashboard route → 401/403, never data.
        key, plaintext, _ = await _key_and_agent(db_session, test_workspace, test_user)
        machine = await client.get(
            f"/api/workspaces/{test_workspace.id}/agents", headers=auth(plaintext)
        )
        assert machine.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_revoked_disabled_expired_keys_are_401(
        self, client, test_workspace, test_user, db_session
    ):
        from datetime import datetime, timedelta, timezone

        key, plaintext, _ = await _key_and_agent(db_session, test_workspace, test_user)
        url = "/v1/chat"

        key.disabled_at = datetime.now(timezone.utc)
        db_session.add(key)
        await db_session.commit()
        disabled = await client.post(
            url, json={"agent_id": "x", "message": "hi"}, headers=auth(plaintext)
        )
        assert disabled.status_code == 401
        assert disabled.json()["error"]["code"] == "key_disabled"

        key.disabled_at = None
        key.revoked_at = datetime.now(timezone.utc)
        db_session.add(key)
        await db_session.commit()
        revoked = await client.post(
            url, json={"agent_id": "x", "message": "hi"}, headers=auth(plaintext)
        )
        assert revoked.json()["error"]["code"] == "invalid_api_key"

        key.revoked_at = None
        key.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.add(key)
        await db_session.commit()
        expired = await client.post(
            url, json={"agent_id": "x", "message": "hi"}, headers=auth(plaintext)
        )
        assert expired.json()["error"]["code"] == "key_expired"


class TestChat:
    @pytest.mark.asyncio
    async def test_stateless_turn_creates_session_execution_and_reply(
        self, client, test_workspace, test_user, db_session, session_factory,
        monkeypatch, encryption_key,
    ):
        key, plaintext, agent = await _key_and_agent(db_session, test_workspace, test_user)
        _install(monkeypatch, session_factory)

        response = await client.post(
            "/v1/chat",
            json={"agent_id": agent.id, "message": "hi"},
            headers=auth(plaintext),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["content"] == "Hello"
        assert body["status"] == "completed"
        assert body["conversation_id"]

        # One Execution row, marked as an API call and tied to the key.
        execution = (
            await db_session.get(Execution, body["execution_id"])
        )
        assert execution is not None
        assert execution.trigger_type == "api"
        assert execution.api_key_id == key.id
        assert execution.status == "completed"

        # The session is stamped with the key and the turn is replayable.
        session = await db_session.get(ChatSession, body["conversation_id"])
        assert session.api_key_id == key.id
        messages = (
            await db_session.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.seq)
            )
        ).scalars().all()
        assert [m.role for m in messages] == ["user", "assistant"]

    @pytest.mark.asyncio
    async def test_conversation_id_continues_with_history(
        self, client, test_workspace, test_user, db_session, session_factory,
        monkeypatch, encryption_key,
    ):
        key, plaintext, agent = await _key_and_agent(db_session, test_workspace, test_user)
        graph = FakeGraphV2()
        monkeypatch.setattr("app.services.agent_runtime.async_session", session_factory)
        monkeypatch.setattr("app.services.agent_runtime.build_graph", lambda *a, **k: graph)

        first = await client.post(
            "/v1/chat",
            json={"agent_id": agent.id, "message": "hi"},
            headers=auth(plaintext),
        )
        conversation_id = first.json()["conversation_id"]

        second = await client.post(
            "/v1/chat",
            json={"message": "again", "conversation_id": conversation_id},
            headers=auth(plaintext),
        )
        assert second.status_code == 200, second.text
        assert second.json()["conversation_id"] == conversation_id

        # Turn two saw the persisted history from turn one.
        history = graph.payloads[1]["messages"]
        assert [type(m).__name__ for m in history] == [
            "HumanMessage", "AIMessage", "HumanMessage",
        ]

    @pytest.mark.asyncio
    async def test_foreign_conversation_is_404_and_touches_nothing(
        self, client, test_workspace, test_user, db_session, session_factory,
        monkeypatch, encryption_key,
    ):
        key, plaintext, agent = await _key_and_agent(db_session, test_workspace, test_user)
        # A session created WITHOUT the key (a builder's Playground thread).
        foreign = ChatSession(workspace_id=test_workspace.id, agent_id=agent.id)
        db_session.add(foreign)
        await db_session.commit()

        _install(monkeypatch, session_factory)
        response = await client.post(
            "/v1/chat",
            json={"message": "hi", "conversation_id": foreign.id},
            headers=auth(plaintext),
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "conversation_not_found"

        # Nothing was persisted against the foreign thread.
        messages = (
            await db_session.execute(
                select(ChatMessage).where(ChatMessage.session_id == foreign.id)
            )
        ).scalars().all()
        assert messages == []

    @pytest.mark.asyncio
    async def test_agent_mismatch_is_409(
        self, client, test_workspace, test_user, db_session, session_factory,
        monkeypatch, encryption_key,
    ):
        key, plaintext, agent = await _key_and_agent(db_session, test_workspace, test_user)
        profile = make_profile(test_workspace.id)
        db_session.add(profile)
        await db_session.flush()
        other_agent = Agent(
            workspace_id=test_workspace.id,
            name="Other",
            llm_profile_id=profile.id,
            system_prompt="",
            params={},
        )
        db_session.add(other_agent)
        await db_session.commit()
        await db_session.refresh(other_agent)

        _install(monkeypatch, session_factory)
        first = await client.post(
            "/v1/chat", json={"agent_id": agent.id, "message": "hi"}, headers=auth(plaintext)
        )
        conversation_id = first.json()["conversation_id"]
        mismatch = await client.post(
            "/v1/chat",
            json={"agent_id": other_agent.id, "message": "hi", "conversation_id": conversation_id},
            headers=auth(plaintext),
        )
        assert mismatch.status_code == 409
        assert mismatch.json()["error"]["code"] == "agent_mismatch"

    @pytest.mark.asyncio
    async def test_streaming_returns_v2_events(
        self, client, test_workspace, test_user, db_session, session_factory,
        monkeypatch, encryption_key,
    ):
        key, plaintext, agent = await _key_and_agent(db_session, test_workspace, test_user)
        _install(monkeypatch, session_factory)

        response = await client.post(
            "/v1/chat",
            json={"agent_id": agent.id, "message": "hi", "stream": True},
            headers=auth(plaintext),
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: message" in response.text
        assert "event: token" in response.text
        # Exactly one terminal done event, carrying usage.
        assert response.text.count("event: done") == 1
        assert '"input_tokens": 10' in response.text

    @pytest.mark.asyncio
    async def test_agent_list_has_no_prompts(
        self, client, test_workspace, test_user, db_session
    ):
        _, plaintext, agent = await _key_and_agent(db_session, test_workspace, test_user)
        response = await client.get("/v1/agent", headers=auth(plaintext))
        assert response.status_code == 200
        entry = response.json()["agents"][0]
        assert set(entry.keys()) == {"id", "name", "description", "status"}
        assert "system_prompt" not in entry


@pytest.mark.asyncio
async def test_v1_openapi_does_not_leak_internal_routes(client):
    openapi = (await client.get("/v1/openapi.json")).json()
    paths = list(openapi["paths"].keys())
    # The sub-app sees paths without the mount prefix; the isolation property
    # is that the two documents share no routes.
    assert set(paths) == {"/chat", "/agent", "/health"}
    internal = (await client.get("/openapi.json")).json()
    assert not any(path in internal["paths"] for path in ("/v1/chat", "/v1/agent"))


@pytest.mark.asyncio
async def test_public_health_is_unauthenticated(client):
    assert (await client.get("/v1/health")).json() == {"status": "ok"}
