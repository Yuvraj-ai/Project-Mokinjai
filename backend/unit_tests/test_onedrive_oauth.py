"""Microsoft OAuth: the authorize URL, the signed state, and token storage.

No test opens a socket: the token endpoint is an httpx.MockTransport, and the callback
tests replace the service call itself so the route's storage and redirect behaviour is
what is under test.
"""

from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select

from app.crypto import decrypt_api_key
from app.models.cloud_connection import CloudConnection
from app.services import cloud_connections as connection_store
from app.services import onedrive

SETTINGS = SimpleNamespace(
    MS_CLIENT_ID="client-id",
    MS_CLIENT_SECRET="client-secret",
    MS_REDIRECT_URI="https://api.test/api/cloud-connections/onedrive/callback",
    FRONTEND_URL="https://app.test",
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ALGORITHM="HS256",
)


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    monkeypatch.setattr(onedrive, "get_settings", lambda: SETTINGS)
    import app.routers.cloud_connections as router_module

    monkeypatch.setattr(router_module, "get_settings", lambda: SETTINGS)
    return SETTINGS


def test_the_authorize_url_asks_for_files_read_and_offline_access():
    url = onedrive.authorize_url("user-1")

    assert url.startswith("https://login.microsoftonline.com/common/oauth2/v2.0/authorize")
    assert "Files.Read" in url
    assert "offline_access" in url.replace("%20", " ")
    assert "state=" in url


def test_the_state_is_signed_and_carries_the_user():
    state = onedrive.build_state("user-1")

    payload = onedrive.decode_state(state)

    assert payload["sub"] == "user-1"
    assert payload["purpose"] == "oauth_state"


async def make_connection(db_session, user_id, token="old-refresh"):
    return await connection_store.save_connection(
        db_session,
        user_id=user_id,
        provider="onedrive",
        refresh_token=token,
        account_label="me@example.com",
    )


@pytest.mark.asyncio
async def test_a_tampered_state_is_rejected(client, db_session):
    response = await client.get(
        "/api/cloud-connections/onedrive/callback",
        params={"code": "code", "state": "not-a-jwt"},
    )

    assert response.status_code == 400
    count = await db_session.scalar(select(func.count()).select_from(CloudConnection))
    assert count == 0


@pytest.mark.asyncio
async def test_the_callback_exchanges_the_code_and_stores_a_token(
    client, db_session, test_user, monkeypatch
):
    async def exchange(code):
        assert code == "the-code"
        return {"refresh_token": "the-refresh-token", "access_token": "unused"}

    monkeypatch.setattr(onedrive, "exchange_code", exchange)
    state = onedrive.build_state(test_user.id)

    response = await client.get(
        "/api/cloud-connections/onedrive/callback",
        params={"code": "the-code", "state": state},
    )

    assert response.status_code == 302
    stored = await connection_store.get_connection(
        db_session, user_id=test_user.id, provider="onedrive"
    )
    assert decrypt_api_key(stored.refresh_token_encrypted) == "the-refresh-token"


@pytest.mark.asyncio
async def test_the_callback_redirects_to_the_files_page(client, test_user, monkeypatch):
    async def exchange(_code):
        return {"refresh_token": "the-refresh-token"}

    monkeypatch.setattr(onedrive, "exchange_code", exchange)

    response = await client.get(
        "/api/cloud-connections/onedrive/callback",
        params={"code": "code", "state": onedrive.build_state(test_user.id)},
    )

    assert response.status_code == 302
    assert response.headers["location"] == "https://app.test/files?onedrive=connected"


@pytest.mark.asyncio
async def test_a_token_endpoint_error_redirects_with_a_failure_flag(
    client, db_session, test_user, monkeypatch
):
    async def exchange(_code):
        raise onedrive.OneDriveAuthError("bad code")

    monkeypatch.setattr(onedrive, "exchange_code", exchange)

    response = await client.get(
        "/api/cloud-connections/onedrive/callback",
        params={"code": "code", "state": onedrive.build_state(test_user.id)},
    )

    assert response.status_code == 302
    assert response.headers["location"] == "https://app.test/files?onedrive=failed"
    count = await db_session.scalar(select(func.count()).select_from(CloudConnection))
    assert count == 0


@pytest.mark.asyncio
async def test_the_connection_list_never_returns_a_token(
    client, auth_headers, db_session, test_user
):
    await make_connection(db_session, test_user.id)

    response = await client.get("/api/cloud-connections", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()[0]["provider"] == "onedrive"
    assert "old-refresh" not in response.text
    assert "encrypted" not in response.text


@pytest.mark.asyncio
async def test_a_rotated_refresh_token_is_written_back(db_session, test_user, monkeypatch):
    connection = await make_connection(db_session, test_user.id)

    def handler(request):
        assert request.url.path == "/common/oauth2/v2.0/token"
        return httpx.Response(
            200,
            json={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            },
        )

    access = await onedrive.access_token_for(
        db_session, connection, transport=httpx.MockTransport(handler)
    )

    reloaded = await connection_store.get_connection(
        db_session, user_id=test_user.id, provider="onedrive"
    )
    assert access == "new-access"
    assert decrypt_api_key(reloaded.refresh_token_encrypted) == "new-refresh"
    assert decrypt_api_key(reloaded.refresh_token_encrypted) != "old-refresh"
