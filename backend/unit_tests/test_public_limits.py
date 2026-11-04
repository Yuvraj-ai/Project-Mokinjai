"""Rate and credit limits on /v1 (plan Task 4).

The enforcement order is auth → revoked/disabled → expiry → credit limit →
rate limit, all before any model call. The Redis limiter fails open when
Redis is unreachable: the product stays up, the abuse window is logged.
"""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.config import get_settings
from app.models.api_key import ApiKey
from app.models.execution import Execution
from app.services.api_keys import create_key

from unit_tests.test_public_api import FakeGraphV2, make_profile, auth, _key_and_agent, _install


@pytest.fixture
def encryption_key():
    settings = get_settings()
    previous = getattr(settings, "LLM_ENCRYPTION_KEY", "")
    settings.LLM_ENCRYPTION_KEY = Fernet.generate_key().decode()
    yield settings.LLM_ENCRYPTION_KEY
    settings.LLM_ENCRYPTION_KEY = previous


def _fake_redis(monkeypatch, calls: dict | None = None):
    """An in-memory stand-in patched over the limiter's module singleton, so
    the tests never depend on a live Redis."""

    class FakeRedis:
        def __init__(self):
            self.data = {}
            self.available = True
            self.calls = calls if calls is not None else {}

        def incr(self, key):
            self.calls["incr"] = self.calls.get("incr", 0) + 1
            if not self.available:
                raise ConnectionError("redis down")
            self.data[key] = self.data.get(key, 0) + 1
            return self.data[key]

        def expire(self, key, seconds):
            self.calls["expire"] = self.calls.get("expire", 0) + 1

    fake = FakeRedis()
    monkeypatch.setattr("app.services.public_limits._redis", fake)
    return fake


@pytest.mark.asyncio
async def test_credit_limit_refuses_before_the_model_runs(
    client, test_workspace, test_user, db_session, session_factory,
    monkeypatch, encryption_key,
):
    from datetime import datetime, timezone
    from decimal import Decimal

    key, plaintext, agent = await _key_and_agent(db_session, test_workspace, test_user)
    key.credit_limit_usd = Decimal("0.001")
    key.spend_window_started_at = datetime.now(timezone.utc)
    db_session.add(key)
    # A prior completed execution already at the limit.
    db_session.add(
        Execution(
            workspace_id=test_workspace.id,
            agent_id=agent.id,
            api_key_id=key.id,
            status="completed",
            trigger_type="api",
            cost_usd=Decimal("0.0005"),
        )
    )
    await db_session.commit()

    graph_called = {"called": False}

    def spy_graph(*a, **k):
        graph_called["called"] = True
        return FakeGraphV2()

    monkeypatch.setattr("app.services.agent_runtime.async_session", session_factory)
    monkeypatch.setattr("app.services.agent_runtime.build_graph", spy_graph)
    _fake_redis(monkeypatch)

    response = await client.post(
        "/v1/chat", json={"agent_id": agent.id, "message": "hi"}, headers=auth(plaintext)
    )
    assert response.status_code == 402
    assert response.json()["error"]["code"] == "credit_limit_exceeded"
    # The refusal happened before any model call or doomed execution row.
    assert graph_called["called"] is False
    executions = (
        await db_session.execute(
            select(Execution).where(Execution.api_key_id == key.id, Execution.status == "running")
        )
    ).scalars().all()
    assert executions == []


@pytest.mark.asyncio
async def test_rate_limit_429_with_retry_after_and_reset(
    client, test_workspace, test_user, db_session, session_factory,
    monkeypatch, encryption_key,
):
    key, plaintext, agent = await _key_and_agent(db_session, test_workspace, test_user)
    monkeypatch.setattr("app.services.agent_runtime.async_session", session_factory)
    monkeypatch.setattr("app.services.agent_runtime.build_graph", lambda *a, **k: FakeGraphV2())
    fake = _fake_redis(monkeypatch)
    monkeypatch.setattr(
        "app.services.public_limits.get_settings",
        lambda: type("S", (), {"PUBLIC_API_RATE_LIMIT_PER_MINUTE": 2})(),
    )

    url = "/v1/chat"
    first = await client.post(url, json={"agent_id": agent.id, "message": "hi"}, headers=auth(plaintext))
    assert first.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "2"
    second = await client.post(url, json={"agent_id": agent.id, "message": "hi"}, headers=auth(plaintext))
    assert second.status_code == 200
    third = await client.post(url, json={"agent_id": agent.id, "message": "hi"}, headers=auth(plaintext))
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limit_exceeded"
    assert "Retry-After" in third.headers

    # The counter resets after the window: expire the entry and go again.
    fake.data.clear()
    fourth = await client.post(url, json={"agent_id": agent.id, "message": "hi"}, headers=auth(plaintext))
    assert fourth.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_fails_open_when_redis_is_down(
    client, test_workspace, test_user, db_session, session_factory,
    monkeypatch, encryption_key,
):
    key, plaintext, agent = await _key_and_agent(db_session, test_workspace, test_user)
    _install(monkeypatch, session_factory)
    fake = _fake_redis(monkeypatch)
    fake.available = False
    # The settings fake has no REDIS_URL: if the limiter tried to build a new
    # client it would error — with _redis patched the test proves fail-open.
    monkeypatch.setattr(
        "app.services.public_limits.get_settings",
        lambda: type("S", (), {"PUBLIC_API_RATE_LIMIT_PER_MINUTE": 2})(),
    )

    response = await client.post(
        "/v1/chat", json={"agent_id": agent.id, "message": "hi"}, headers=auth(plaintext)
    )
    # Fail open: the request proceeds even though Redis is unreachable.
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_disabled_key_short_circuits_before_limits(
    client, test_workspace, test_user, db_session, session_factory,
    monkeypatch, encryption_key,
):
    from datetime import datetime, timezone

    key, plaintext, agent = await _key_and_agent(db_session, test_workspace, test_user)
    key.disabled_at = datetime.now(timezone.utc)
    db_session.add(key)
    await db_session.commit()

    calls = {}
    _fake_redis(monkeypatch, calls)
    response = await client.post(
        "/v1/chat", json={"agent_id": agent.id, "message": "hi"}, headers=auth(plaintext)
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "key_disabled"
    # The limiter was never consulted.
    assert calls.get("incr", 0) == 0
