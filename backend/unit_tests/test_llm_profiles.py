"""LLM profile test-connection is the save gate.

A provider failure still persists a failed row and returns the provider error.
A missing context window on an unknown model does not persist anything.
"""

import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.services.llm_probe import LlmProbeError


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
