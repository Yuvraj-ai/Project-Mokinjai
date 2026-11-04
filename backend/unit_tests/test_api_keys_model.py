"""API key model behaviour (plan Task 1): hashing, one-time plaintext, lazy
spend windows, lifecycle audit."""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select

from app.models.api_key import ApiKey, AuditLog
from app.models.execution import Execution
from app.services.api_keys import (
    audit,
    create_key,
    generate_api_key,
    hash_secret,
    spend_in_window,
)


def test_generate_api_key_shape():
    key = generate_api_key()
    assert key.startswith("mk_")
    assert len(key) > 40
    assert generate_api_key() != key


def test_hash_secret_is_sha256_hex_of_plaintext():
    import hashlib

    plaintext = generate_api_key()
    assert hash_secret(plaintext) == hashlib.sha256(plaintext.encode()).hexdigest()


@pytest.mark.asyncio
async def test_create_key_persists_hash_and_prefix_once(db_session, test_workspace, test_user):
    key, plaintext = await create_key(
        db_session,
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        name="Chatbot Key",
    )
    assert plaintext.startswith("mk_")
    assert key.key_hash == hash_secret(plaintext)
    assert key.key_hash != plaintext
    assert plaintext.startswith(key.prefix)
    assert key.credit_limit_usd is None  # unlimited by default
    await db_session.refresh(key)
    # The audit trail recorded the creation.
    audits = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.resource_type == "api_key")
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].action == "created"


@pytest.mark.asyncio
async def test_spend_in_window_sums_executions_since_window_start(
    db_session, test_workspace, test_user
):
    key, _ = await create_key(db_session, workspace_id=test_workspace.id, user_id=test_user.id, name="K")
    now = datetime.now(timezone.utc)
    key.spend_window_started_at = now - timedelta(days=3)
    db_session.add(key)

    def execution(cost: float, created: datetime) -> Execution:
        return Execution(
            workspace_id=test_workspace.id,
            api_key_id=key.id,
            status="completed",
            trigger_type="api",
            cost_usd=Decimal(str(cost)),
            created_at=created,
        )

    db_session.add_all(
        [
            execution(0.10, now - timedelta(days=1)),   # inside the window
            execution(0.20, now - timedelta(hours=2)),  # inside
            execution(9.99, now - timedelta(days=5)),   # before the window
        ]
    )
    await db_session.commit()

    spend = await spend_in_window(db_session, key)
    assert spend == Decimal("0.3")


@pytest.mark.asyncio
async def test_spend_window_rolls_lazily_when_period_elapsed(
    db_session, test_workspace, test_user
):
    key, _ = await create_key(
        db_session,
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        name="K",
        credit_reset_period="weekly",
    )
    now = datetime.now(timezone.utc)
    key.spend_window_started_at = now - timedelta(days=8)  # weekly window elapsed
    db_session.add(key)
    old_start = key.spend_window_started_at

    db_session.add(
        Execution(
            workspace_id=test_workspace.id,
            api_key_id=key.id,
            status="completed",
            trigger_type="api",
            cost_usd=Decimal("9.99"),
            created_at=now - timedelta(days=5),  # inside the OLD window
        )
    )
    await db_session.commit()

    spend = await spend_in_window(db_session, key)

    # The window rolled forward: the old-window spend is not counted, and the
    # anchor moved to (approximately) now.
    assert spend == Decimal("0")
    await db_session.refresh(key)
    assert key.spend_window_started_at > old_start
