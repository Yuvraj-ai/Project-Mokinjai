"""Search API keys are write-only: stored encrypted, reported as a boolean."""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.config import get_settings
from app.models.search_credential import SearchCredential


@pytest.fixture
def encryption_key():
    settings = get_settings()
    previous = getattr(settings, "LLM_ENCRYPTION_KEY", "")
    settings.LLM_ENCRYPTION_KEY = Fernet.generate_key().decode()
    yield settings.LLM_ENCRYPTION_KEY
    settings.LLM_ENCRYPTION_KEY = previous


def url(workspace_id: str) -> str:
    return f"/api/workspaces/{workspace_id}/search-credentials"


@pytest.mark.asyncio
async def test_upsert_list_and_delete(client, test_workspace, auth_headers, encryption_key, db_session):
    base = url(test_workspace.id)

    listed = await client.get(base, headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json() == [
        {"provider": "tavily", "has_key": False},
        {"provider": "exa", "has_key": False},
    ]

    saved = await client.put(
        f"{base}/tavily", json={"api_key": "tvly-secret"}, headers=auth_headers
    )
    assert saved.status_code == 200
    assert saved.json() == {"provider": "tavily", "has_key": True}
    assert "tvly-secret" not in saved.text

    row = (
        await db_session.execute(
            select(SearchCredential).where(SearchCredential.workspace_id == test_workspace.id)
        )
    ).scalar_one()
    assert row.encrypted_api_key != b"tvly-secret"

    replaced = await client.put(
        f"{base}/tavily", json={"api_key": "tvly-rotated"}, headers=auth_headers
    )
    assert replaced.status_code == 200
    listed = await client.get(base, headers=auth_headers)
    assert [item for item in listed.json() if item["provider"] == "tavily"][0]["has_key"] is True

    deleted = await client.delete(f"{base}/tavily", headers=auth_headers)
    assert deleted.status_code == 204
    listed = await client.get(base, headers=auth_headers)
    assert all(item["has_key"] is False for item in listed.json())


@pytest.mark.asyncio
async def test_unknown_provider_is_refused(client, test_workspace, auth_headers, encryption_key):
    response = await client.put(
        f"{url(test_workspace.id)}/google",
        json={"api_key": "key"},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_viewers_cannot_change_keys(
    client, test_workspace, viewer_headers, auth_headers, encryption_key
):
    assert (await client.get(url(test_workspace.id), headers=viewer_headers)).status_code == 200
    denied = await client.put(
        f"{url(test_workspace.id)}/exa",
        json={"api_key": "key"},
        headers=viewer_headers,
    )
    assert denied.status_code == 403
