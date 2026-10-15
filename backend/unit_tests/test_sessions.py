"""Server-side sessions.

A session row is what makes logout mean something: it is the only record that a
given refresh token is allowed to exist, and marking it revoked ends that device's
access on the next request.
"""

from datetime import datetime, timedelta, timezone

from app.models.session import Session


async def test_session_persists_and_round_trips(db_session, test_user):
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    db_session.add(
        Session(
            user_id=test_user.id,
            token_hash="a" * 64,
            expires_at=expires,
        )
    )
    await db_session.commit()

    from sqlalchemy import select

    found = (
        await db_session.execute(
            select(Session).where(Session.token_hash == "a" * 64)
        )
    ).scalar_one()

    assert found.user_id == test_user.id
    assert found.revoked_at is None
    assert found.created_at is not None, "created_at should come from the server default"
    assert found.last_used_at is not None, "last_used_at should come from the server default"


from app.services.sessions import (
    create_session,
    get_live_session,
    hash_token,
    new_refresh_token,
    prune_expired_sessions,
    revoke_all_sessions,
    revoke_session,
)


def test_refresh_tokens_are_random_256_bit_strings():
    first, second = new_refresh_token(), new_refresh_token()
    assert first != second
    assert len(first) >= 32


def test_refresh_tokens_are_stored_only_as_a_hash():
    token = new_refresh_token()
    digest = hash_token(token)
    assert digest != token
    assert len(digest) == 64


async def test_create_session_stores_the_hash_not_the_token(db_session, test_user):
    token = new_refresh_token()
    session = await create_session(db_session, user_id=test_user.id, refresh_token=token)

    assert session.token_hash == hash_token(token)
    assert token not in session.token_hash


async def test_get_live_session_finds_a_fresh_session(db_session, test_user):
    token = new_refresh_token()
    created = await create_session(db_session, user_id=test_user.id, refresh_token=token)

    found = await get_live_session(db_session, token)

    assert found is not None
    assert found.id == created.id


async def test_get_live_session_rejects_an_unknown_token(db_session):
    assert await get_live_session(db_session, new_refresh_token()) is None


async def test_get_live_session_rejects_a_revoked_session(db_session, test_user):
    token = new_refresh_token()
    session = await create_session(db_session, user_id=test_user.id, refresh_token=token)

    await revoke_session(db_session, session)

    assert await get_live_session(db_session, token) is None


async def test_get_live_session_rejects_an_expired_session(db_session, test_user):
    token = new_refresh_token()
    session = await create_session(db_session, user_id=test_user.id, refresh_token=token)

    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    assert await get_live_session(db_session, token) is None


async def test_a_fourth_session_evicts_the_oldest(db_session, test_user):
    tokens = []
    for index in range(3):
        token = new_refresh_token()
        tokens.append(token)
        session = await create_session(db_session, user_id=test_user.id, refresh_token=token)
        # Distinct, increasing recency. Equal timestamps would leave the ORDER BY
        # nondeterministic and make this test flaky rather than wrong.
        session.last_used_at = datetime.now(timezone.utc) - timedelta(minutes=10 * (3 - index))
        await db_session.commit()

    await create_session(db_session, user_id=test_user.id, refresh_token=new_refresh_token())

    live = [
        await get_live_session(db_session, token) for token in tokens
    ]
    assert sum(1 for s in live if s is not None) == 2, "the oldest should have been evicted"
    assert live[0] is None, "the first-created session is the one that goes"


async def test_revoke_all_sessions_leaves_other_users_alone(db_session, test_user, admin_user):
    mine = new_refresh_token()
    theirs = new_refresh_token()
    await create_session(db_session, user_id=test_user.id, refresh_token=mine)
    await create_session(db_session, user_id=admin_user.id, refresh_token=theirs)

    revoked = await revoke_all_sessions(db_session, test_user.id)

    assert revoked == 1
    assert await get_live_session(db_session, mine) is None
    assert await get_live_session(db_session, theirs) is not None


async def test_prune_deletes_only_long_expired_sessions(db_session, test_user):
    stale = new_refresh_token()
    fresh = new_refresh_token()
    old = await create_session(db_session, user_id=test_user.id, refresh_token=stale)
    await create_session(db_session, user_id=test_user.id, refresh_token=fresh)

    old.expires_at = datetime.now(timezone.utc) - timedelta(days=60)
    await db_session.commit()

    removed = await prune_expired_sessions(db_session, retention_days=30)

    assert removed == 1
    assert await get_live_session(db_session, stale) is None
    assert await get_live_session(db_session, fresh) is not None


import asyncio

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


@pytest_asyncio.fixture(scope="function")
async def service_session(engine):
    """A session the test drives itself, separate from the client's per-request one."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


from sqlalchemy import select

from app.models.session import Session


async def test_login_creates_a_session(client, test_user, service_session):
    response = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )

    assert response.status_code == 200, response.text
    body = response.json()

    stored = (await service_session.execute(select(Session))).scalar_one()
    assert stored.token_hash == hash_token(body["refresh_token"])
    assert body["refresh_token"] not in stored.token_hash


async def test_login_access_token_carries_a_session_id(client, test_user, service_session):
    from app.utils.security import decode_token

    response = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    payload = decode_token(response.json()["access_token"])

    session = (await service_session.execute(select(Session))).scalar_one()
    assert payload["sid"] == session.id


async def test_refresh_works_for_a_live_session(client, test_user):
    login = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    refresh_token = login.json()["refresh_token"]

    response = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


async def test_refresh_advances_last_used_at(client, test_user, service_session):
    """The eviction order depends on this write reaching the database.

    Without a commit in the refresh path the assignment is discarded when the
    request's session closes, and eviction silently degrades from
    least-recently-used to oldest-created. Nothing else in the suite would notice.
    """
    login = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    refresh_token = login.json()["refresh_token"]

    before = (await service_session.execute(select(Session))).scalar_one().last_used_at
    await asyncio.sleep(0.01)  # timestamptz is microsecond-precision; make the delta real
    refreshed = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200, refreshed.text

    service_session.expire_all()  # drop the cached row, so the next read hits the database
    after = (await service_session.execute(select(Session))).scalar_one().last_used_at

    assert after > before, "refresh must persist last_used_at, or eviction is not LRU"


async def test_refresh_fails_for_a_revoked_session(client, test_user, service_session):
    login = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    refresh_token = login.json()["refresh_token"]

    session = (await service_session.execute(select(Session))).scalar_one()
    await revoke_session(service_session, session)

    response = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 401, response.text


async def test_a_refresh_token_that_was_never_issued_is_rejected(client):
    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": new_refresh_token()}
    )

    assert response.status_code == 401, response.text


async def test_a_revoked_session_rejects_a_still_valid_access_token(
    client, auth_headers, service_session
):
    """The defect being fixed: logout must end access, not wait 30 minutes.

    The access token below is untouched and unexpired. Only its session is revoked.
    """
    ok = await client.get("/api/auth/me", headers=auth_headers)
    assert ok.status_code == 200, ok.text

    session = (await service_session.execute(select(Session))).scalar_one()
    await revoke_session(service_session, session)

    rejected = await client.get("/api/auth/me", headers=auth_headers)
    assert rejected.status_code == 401, rejected.text


async def test_a_token_without_a_session_id_is_rejected(client, test_user):
    """Tokens issued before server-side sessions cannot be validated, so they fail."""
    from app.utils.security import create_access_token

    stale = create_access_token({"sub": test_user.id, "email": test_user.email})
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {stale}"})

    assert response.status_code == 401, response.text


async def test_logout_revokes_the_callers_session(client, auth_headers):
    assert (await client.get("/api/auth/me", headers=auth_headers)).status_code == 200

    out = await client.post("/api/auth/logout", headers=auth_headers)
    assert out.status_code == 200, out.text

    assert (await client.get("/api/auth/me", headers=auth_headers)).status_code == 401


async def test_logout_all_revokes_every_session_for_that_user(client, test_user):
    login = await client.post(
        "/api/auth/login",
        json={"email": "test@example.com", "password": "testpass123"},
    )
    second_token = login.json()["refresh_token"]

    response = await client.post("/api/auth/login", json={"email": "test@example.com", "password": "testpass123"})
    first_token = response.json()["refresh_token"]

    # Log out the second device, then end the rest.
    assert (await client.post("/api/auth/refresh", json={"refresh_token": first_token})).status_code == 200
    await client.post("/api/auth/logout-all", headers={"Authorization": f"Bearer {response.json()['access_token']}"})

    assert (await client.post("/api/auth/refresh", json={"refresh_token": first_token})).status_code == 401
    assert (await client.post("/api/auth/refresh", json={"refresh_token": second_token})).status_code == 401
