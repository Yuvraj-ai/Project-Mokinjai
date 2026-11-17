"""Per-user cloud connection storage. The refresh token never leaves encrypted."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import encrypt_api_key
from app.models.cloud_connection import CloudConnection


async def save_connection(
    db: AsyncSession,
    *,
    user_id: str,
    provider: str,
    refresh_token: str,
    account_label: str | None,
) -> CloudConnection:
    """Upsert by `(user_id, provider)`: one connection per provider per person."""
    row = await get_connection(db, user_id=user_id, provider=provider)
    encrypted = encrypt_api_key(refresh_token)
    if row is None:
        row = CloudConnection(
            user_id=user_id,
            provider=provider,
            account_label=account_label,
            refresh_token_encrypted=encrypted,
        )
        db.add(row)
    else:
        row.account_label = account_label
        row.refresh_token_encrypted = encrypted
    await db.commit()
    await db.refresh(row)
    return row


async def get_connection(
    db: AsyncSession, *, user_id: str, provider: str
) -> CloudConnection | None:
    result = await db.execute(
        select(CloudConnection).where(
            CloudConnection.user_id == user_id,
            CloudConnection.provider == provider,
        )
    )
    return result.scalar_one_or_none()


async def delete_connection(db: AsyncSession, *, user_id: str, provider: str) -> bool:
    result = await db.execute(
        delete(CloudConnection).where(
            CloudConnection.user_id == user_id,
            CloudConnection.provider == provider,
        )
    )
    await db.commit()
    return result.rowcount > 0
