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
