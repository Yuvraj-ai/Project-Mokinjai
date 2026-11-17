"""The per-user connection store: encrypted at rest, upsert by provider."""

import pytest
from sqlalchemy import func, select

from app.crypto import decrypt_api_key
from app.models.cloud_connection import CloudConnection
from app.services import cloud_connections as service


@pytest.mark.asyncio
async def test_saving_a_token_stores_ciphertext(db_session, test_user):
    connection = await service.save_connection(
        db_session,
        user_id=test_user.id,
        provider="onedrive",
        refresh_token="plain-refresh-token",
        account_label="me@example.com",
    )

    assert connection.refresh_token_encrypted != b"plain-refresh-token"
    assert b"plain-refresh-token" not in connection.refresh_token_encrypted
    assert decrypt_api_key(connection.refresh_token_encrypted) == "plain-refresh-token"


@pytest.mark.asyncio
async def test_loading_returns_the_plaintext(db_session, test_user):
    await service.save_connection(
        db_session,
        user_id=test_user.id,
        provider="onedrive",
        refresh_token="plain-refresh-token",
        account_label=None,
    )

    loaded = await service.get_connection(db_session, user_id=test_user.id, provider="onedrive")

    assert loaded is not None
    assert decrypt_api_key(loaded.refresh_token_encrypted) == "plain-refresh-token"


@pytest.mark.asyncio
async def test_saving_twice_updates_the_row(db_session, test_user):
    await service.save_connection(
        db_session, user_id=test_user.id, provider="onedrive",
        refresh_token="first", account_label="one",
    )
    await service.save_connection(
        db_session, user_id=test_user.id, provider="onedrive",
        refresh_token="second", account_label="two",
    )

    count = await db_session.scalar(select(func.count()).select_from(CloudConnection))
    loaded = await service.get_connection(db_session, user_id=test_user.id, provider="onedrive")
    assert count == 1
    assert decrypt_api_key(loaded.refresh_token_encrypted) == "second"
    assert loaded.account_label == "two"


@pytest.mark.asyncio
async def test_deleting_a_connection_removes_it(db_session, test_user):
    await service.save_connection(
        db_session, user_id=test_user.id, provider="onedrive",
        refresh_token="token", account_label=None,
    )

    deleted = await service.delete_connection(
        db_session, user_id=test_user.id, provider="onedrive"
    )

    assert deleted is True
    assert await service.get_connection(db_session, user_id=test_user.id, provider="onedrive") is None


@pytest.mark.asyncio
async def test_an_unknown_connection_is_none(db_session, test_user):
    assert await service.get_connection(
        db_session, user_id=test_user.id, provider="onedrive"
    ) is None
