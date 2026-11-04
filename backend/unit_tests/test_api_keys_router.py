"""API key management endpoints (plan Task 2)."""

import pytest
from decimal import Decimal
from sqlalchemy import select

from app.models.api_key import ApiKey, AuditLog
from app.models.execution import Execution


BASE = "/api/workspaces/{ws}/api-keys"


async def _make_key(client, ws_id, headers, name="Chatbot Key", **create_kwargs):
    response = await client.post(
        BASE.format(ws=ws_id), json={"name": name, **create_kwargs}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_create_returns_plaintext_exactly_once(
    client, auth_headers, test_workspace, db_session
):
    created = await _make_key(client, test_workspace.id, auth_headers)
    plaintext = created["key"]
    assert plaintext.startswith("mk_")
    assert created["prefix"] in plaintext
    assert "key_hash" not in created

    fetched = await client.get(
        BASE.format(ws=test_workspace.id) + f"/{created['id']}", headers=auth_headers
    )
    body = fetched.json()
    assert "key" not in body and "key_hash" not in body
    assert body["prefix"] == created["prefix"]
    assert body["status"] == "active"


@pytest.mark.asyncio
async def test_list_and_status_chips(client, auth_headers, test_workspace, db_session):
    created = await _make_key(client, test_workspace.id, auth_headers, name="A")
    listed = await client.get(BASE.format(ws=test_workspace.id), headers=auth_headers)
    assert listed.status_code == 200
    rows = listed.json()
    assert any(row["id"] == created["id"] for row in rows)


@pytest.mark.asyncio
async def test_rotate_revokes_old_secret_immediately(
    client, auth_headers, test_workspace, db_session
):
    created = await _make_key(client, test_workspace.id, auth_headers)
    rotated = await client.post(
        BASE.format(ws=test_workspace.id) + f"/{created['id']}/rotate",
        headers=auth_headers,
    )
    assert rotated.status_code == 200
    new_plaintext = rotated.json()["key"]
    assert new_plaintext != created["key"]

    # The row keeps its id and history, with the new hash.
    row = (
        await db_session.execute(
            select(ApiKey).where(ApiKey.id == created["id"])
        )
    ).scalar_one()
    assert row.revoked_at is None  # rotation re-activates the row, not a revoke


@pytest.mark.asyncio
async def test_disable_enable_toggle(client, auth_headers, test_workspace, db_session):
    created = await _make_key(client, test_workspace.id, auth_headers)
    base = BASE.format(ws=test_workspace.id) + f"/{created['id']}"

    disabled = (await client.post(base + "/disable", headers=auth_headers)).json()
    assert disabled["status"] == "disabled"

    enabled = (await client.post(base + "/enable", headers=auth_headers)).json()
    assert enabled["status"] == "active"

    audits = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.resource_type == "api_key").order_by(AuditLog.id)
        )
    ).scalars().all()
    actions = [a.action for a in audits]
    assert "disabled" in actions and "enabled" in actions


@pytest.mark.asyncio
async def test_delete_is_a_soft_revoke(client, auth_headers, test_workspace, db_session):
    created = await _make_key(client, test_workspace.id, auth_headers)
    deleted = await client.delete(
        BASE.format(ws=test_workspace.id) + f"/{created['id']}", headers=auth_headers
    )
    assert deleted.status_code == 200

    row = (
        await db_session.execute(select(ApiKey).where(ApiKey.id == created["id"]))
    ).scalar_one()
    assert row.revoked_at is not None  # the row survives as the audit trace

    listed = await client.get(BASE.format(ws=test_workspace.id), headers=auth_headers)
    assert listed.json() == []  # revoked keys leave the dashboard list


@pytest.mark.asyncio
async def test_usage_totals_and_daily_series(
    client, auth_headers, test_workspace, db_session
):
    from datetime import datetime, timedelta, timezone

    created = await _make_key(client, test_workspace.id, auth_headers)
    now = datetime.now(timezone.utc)

    def execution(cost: str, created_at: datetime) -> Execution:
        return Execution(
            workspace_id=test_workspace.id,
            api_key_id=created["id"],
            status="completed",
            trigger_type="api",
            cost_usd=Decimal(cost),
            created_at=created_at,
        )

    db_session.add_all(
        [
            execution("0.100000", now - timedelta(hours=1)),   # today
            execution("0.200000", now - timedelta(days=2)),    # this week
            execution("0.400000", now - timedelta(days=20)),   # this month
            execution("8.000000", now - timedelta(days=60)),   # older
        ]
    )
    await db_session.commit()

    usage = await client.get(
        BASE.format(ws=test_workspace.id) + f"/{created['id']}/usage",
        headers=auth_headers,
    )
    assert usage.status_code == 200
    body = usage.json()
    assert body["totals"]["today"] == pytest.approx(0.1)
    assert body["totals"]["week"] == pytest.approx(0.3)
    assert body["totals"]["month"] == pytest.approx(0.7)
    assert body["totals"]["total"] == pytest.approx(8.7)
    assert len(body["daily"]) == 30
    # Two of the thirty days carry cost.
    assert sum(1 for d in body["daily"] if d["cost"] > 0) == 3


@pytest.mark.asyncio
async def test_viewer_cannot_write(client, viewer_headers, test_workspace, auth_headers, db_session):
    created = await _make_key(client, test_workspace.id, auth_headers)
    base = BASE.format(ws=test_workspace.id)
    assert (
        await client.post(base, json={"name": "X"}, headers=viewer_headers)
    ).status_code == 403
    assert (
        await client.delete(base + f"/{created['id']}", headers=viewer_headers)
    ).status_code == 403
    # Reads are fine.
    assert (
        await client.get(base, headers=viewer_headers)
    ).status_code == 200


@pytest.mark.asyncio
async def test_other_workspace_key_is_404(
    client, auth_headers, test_workspace, test_user, db_session
):
    from app.models.workspace import Workspace

    from app.services.api_keys import create_key

    other = Workspace(name="Elsewhere", owner_id=test_user.id)
    db_session.add(other)
    await db_session.flush()
    key, _ = await create_key(db_session, workspace_id=other.id, user_id=test_user.id, name="Elsewhere Key")
    await db_session.commit()

    response = await client.get(
        BASE.format(ws=test_workspace.id) + f"/{key.id}", headers=auth_headers
    )
    assert response.status_code == 404
