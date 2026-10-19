"""LLM profile test-connection is the save gate.

A provider failure still persists a failed row and returns the provider error.
A missing context window on an unknown model does not persist anything.
"""

import httpx
import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.services.llm_probe import LlmProbeError, probe_llm


@pytest.fixture
def encryption_key():
    settings = get_settings()
    previous = getattr(settings, "LLM_ENCRYPTION_KEY", "")
    settings.LLM_ENCRYPTION_KEY = Fernet.generate_key().decode()
    yield settings.LLM_ENCRYPTION_KEY
    settings.LLM_ENCRYPTION_KEY = previous


def _body(**overrides):
    payload = {
        "name": "Workhorse",
        "provider": "openai",
        "model_id": "gpt-4o",
        "api_key": "sk-plain-key",
        "input_price_per_million": 2.5,
        "output_price_per_million": 10.0,
        "cache_price_per_million": 1.25,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_failed_probe_saves_flagged_profile_and_returns_provider_error(
    client, auth_headers, test_workspace, encryption_key, monkeypatch
):
    async def fail_probe(**kwargs):
        raise LlmProbeError("invalid api key")

    monkeypatch.setattr("app.routers.llm_profiles.lookup_max_input_tokens", lambda provider, model_id: 128000)
    monkeypatch.setattr("app.routers.llm_profiles.probe_llm", fail_probe)

    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/llm-profiles/test",
        json=_body(),
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["usable"] is False
    assert body["last_error"] == "invalid api key"
    assert body["context_window"] == 128000
    assert body["compaction_at_tokens"] == 102400
    assert "api_key" not in body
    assert "encrypted_api_key" not in body
    assert "sk-plain-key" not in response.text

    listed = await client.get(
        f"/api/workspaces/{test_workspace.id}/llm-profiles",
        headers=auth_headers,
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["profiles"][0]["status"] == "failed"

    usable = await client.get(
        f"/api/workspaces/{test_workspace.id}/llm-profiles?usable=true",
        headers=auth_headers,
    )
    assert usable.json()["total"] == 0
    assert usable.json()["profiles"] == []


@pytest.mark.asyncio
async def test_unknown_model_without_context_window_is_not_saved(
    client, auth_headers, test_workspace, encryption_key, monkeypatch
):
    monkeypatch.setattr("app.routers.llm_profiles.lookup_max_input_tokens", lambda provider, model_id: None)

    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/llm-profiles/test",
        json=_body(model_id="not-a-real-model"),
        headers=auth_headers,
    )

    assert response.status_code == 400
    listed = await client.get(
        f"/api/workspaces/{test_workspace.id}/llm-profiles",
        headers=auth_headers,
    )
    assert listed.json()["total"] == 0


@pytest.mark.asyncio
async def test_passing_probe_saves_verified_profile(
    client, auth_headers, test_workspace, encryption_key, monkeypatch
):
    async def ok_probe(**kwargs):
        return None

    monkeypatch.setattr("app.routers.llm_profiles.lookup_max_input_tokens", lambda provider, model_id: 1000)
    monkeypatch.setattr("app.routers.llm_profiles.probe_llm", ok_probe)

    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/llm-profiles/test",
        json=_body(context_window=10),
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["usable"] is True
    assert body["last_error"] is None
    assert body["context_window"] == 1000

    usable = await client.get(
        f"/api/workspaces/{test_workspace.id}/llm-profiles?usable=true",
        headers=auth_headers,
    )
    assert usable.json()["total"] == 1


@pytest.mark.asyncio
async def test_probe_llm_timeout_raises_llm_probe_error(monkeypatch):
    async def fake_send(*args, **kwargs):
        raise httpx.ReadTimeout("Request timed out")

    monkeypatch.setattr("app.services.llm_probe._send", fake_send)

    with pytest.raises(LlmProbeError) as exc_info:
        await probe_llm(
            provider="openai",
            model_id="gpt-4o",
            api_key="test-key",
            base_url=None,
        )

    assert "Request timed out after 120s" in str(exc_info.value)


@pytest.mark.asyncio
async def test_probe_llm_connect_error_raises_llm_probe_error(monkeypatch):
    async def fake_send(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr("app.services.llm_probe._send", fake_send)

    with pytest.raises(LlmProbeError) as exc_info:
        await probe_llm(
            provider="openai",
            model_id="gpt-4o",
            api_key="test-key",
            base_url=None,
        )

    assert "Connection failed: Connection refused" in str(exc_info.value)


@pytest.mark.asyncio
async def test_router_handles_probe_timeout_as_failed_profile(
    client, auth_headers, test_workspace, encryption_key, monkeypatch
):
    async def timeout_probe(*args, **kwargs):
        raise httpx.ReadTimeout("Request timed out")

    monkeypatch.setattr("app.services.llm_probe._send", timeout_probe)
    monkeypatch.setattr("app.routers.llm_profiles.lookup_max_input_tokens", lambda provider, model_id: 128000)

    response = await client.post(
        f"/api/workspaces/{test_workspace.id}/llm-profiles/test",
        json=_body(),
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["usable"] is False
    assert "timed out after 120s" in body["last_error"]


@pytest.mark.asyncio
async def test_max_output_tokens_is_saved_and_cannot_exceed_the_window(
    client, auth_headers, test_workspace, encryption_key, monkeypatch
):
    async def ok_probe(**kwargs):
        return None

    monkeypatch.setattr("app.routers.llm_profiles.lookup_max_input_tokens", lambda p, m: 1000)
    monkeypatch.setattr("app.routers.llm_profiles.probe_llm", ok_probe)
    base = f"/api/workspaces/{test_workspace.id}/llm-profiles/test"

    saved = await client.post(base, json=_body(max_output_tokens=500), headers=auth_headers)
    assert saved.status_code == 200, saved.text
    assert saved.json()["max_output_tokens"] == 500

    refused = await client.post(base, json=_body(max_output_tokens=1001), headers=auth_headers)
    assert refused.status_code == 400
    assert "context window" in refused.json()["detail"]


@pytest.mark.asyncio
async def test_delete_is_refused_while_an_agent_uses_the_profile(
    client, auth_headers, test_workspace, db_session
):
    from app.models.agent import Agent
    from app.models.llm_profile import LlmProfile

    profile = LlmProfile(
        workspace_id=test_workspace.id,
        name="In use",
        provider="openai",
        model_id="gpt-4o",
        encrypted_api_key=b"ciphertext",
        context_window=128000,
        compaction_at_tokens=102400,
        input_price_per_million=0.0,
        output_price_per_million=0.0,
        cache_price_per_million=0.0,
        status="verified",
    )
    db_session.add(profile)
    await db_session.commit()
    db_session.add(
        Agent(
            workspace_id=test_workspace.id,
            name="Uses it",
            llm_profile_id=profile.id,
            system_prompt="Hi",
        )
    )
    await db_session.commit()

    response = await client.delete(
        f"/api/workspaces/{test_workspace.id}/llm-profiles/{profile.id}",
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert "Uses it" in response.json()["detail"]

