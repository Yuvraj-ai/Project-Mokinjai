"""The daemon's second auth layer: the HMAC header over the request body.

Layer one is InstaBox's private-port bearer token, which the proxy checks before the
request ever reaches us. This layer is ours, so it can be rotated independently and a
request that fails it costs a comparison rather than a Docker call.
"""

import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.sandbox.daemon import auth
from app.services.sandbox.daemon.app import app

SECRET = "test-daemon-secret"
BODY = b'{"hello":"world"}'
NOW = 1_800_000_000


def test_a_valid_signature_is_accepted():
    header = auth.sign(SECRET, NOW, BODY)

    assert auth.verify(SECRET, header, BODY, now=NOW) is None


def test_a_wrong_secret_is_rejected():
    header = auth.sign("another-secret", NOW, BODY)

    reason = auth.verify(SECRET, header, BODY, now=NOW)

    assert isinstance(reason, str)
    assert reason


def test_a_stale_timestamp_is_rejected():
    header = auth.sign(SECRET, NOW - 600, BODY)

    assert auth.verify(SECRET, header, BODY, now=NOW) == "stale timestamp"


def test_a_tampered_body_is_rejected():
    header = auth.sign(SECRET, NOW, BODY)

    assert auth.verify(SECRET, header, BODY + b"x", now=NOW) == "bad signature"


def test_a_missing_header_is_rejected():
    assert auth.verify(SECRET, None, BODY, now=NOW) == "missing signature"
    assert auth.verify(SECRET, "", BODY, now=NOW) == "missing signature"


@pytest.mark.asyncio
async def test_health_is_unauthenticated_and_answers_status_ok(monkeypatch):
    monkeypatch.setattr("app.services.sandbox.daemon.app.docker_reachable", lambda _bin: True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://daemon") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "docker": True, "sessions": 0}


@pytest.mark.asyncio
async def test_an_oversized_body_is_rejected_before_the_signature_check(monkeypatch):
    import app.services.sandbox.daemon.app as daemon_app

    monkeypatch.setattr(daemon_app, "MAX_REQUEST_OVERHEAD_BYTES", 0)
    monkeypatch.setattr(
        daemon_app,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {"SANDBOX_DAEMON_SECRET": SECRET, "STORAGE_MAX_UPLOAD_BYTES": 10},
        )(),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://daemon") as client:
        response = await client.post("/sessions", content=b"x" * 11)

    assert response.status_code == 413
    assert "upload limit" in response.text


@pytest.mark.asyncio
async def test_fastapi_docs_are_not_exposed(monkeypatch):
    monkeypatch.setattr(
        "app.services.sandbox.daemon.app.get_settings",
        lambda: type(
            "Settings",
            (),
            {"SANDBOX_DAEMON_SECRET": SECRET, "STORAGE_MAX_UPLOAD_BYTES": 95 * 1024 * 1024},
        )(),
    )
    headers = {"X-Mokinjay-Signature": auth.sign(SECRET, int(time.time()), b"")}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://daemon") as client:
        response = await client.get("/openapi.json", headers=headers)

    assert response.status_code == 404
