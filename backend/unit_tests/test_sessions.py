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
