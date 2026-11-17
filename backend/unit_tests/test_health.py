"""The static liveness probe and the database-touching keep-alive probe.

`/health` must stay database-free: Render uses it as the service health check, and a
paused Supabase project must not make the service look dead. `/health/db` is the one a
5-minute monitor pings, so it is also what stops the free Supabase project pausing.
"""

import pytest


@pytest.mark.asyncio
async def test_health_is_static(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_db_reports_ok(client):
    response = await client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.asyncio
async def test_health_db_reports_a_broken_database(client, monkeypatch):
    import app.main as main_module

    class BrokenSession:
        async def __aenter__(self):
            raise RuntimeError("connection refused")

        async def __aexit__(self, *_exc):
            return False

    monkeypatch.setattr(main_module, "async_session", lambda: BrokenSession())

    response = await client.get("/health/db")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
    assert "connection refused" not in response.text
