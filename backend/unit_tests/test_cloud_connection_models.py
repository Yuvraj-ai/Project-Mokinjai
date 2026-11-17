"""The two schema additions: per-user cloud connections and document provenance."""

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.models.cloud_connection import CloudConnection
from app.models.knowledge import DOCUMENT_STATUS_STORED, Document
from app.models.workspace import Workspace


def make_connection(user_id, provider="onedrive", label="me@example.com"):
    return CloudConnection(
        user_id=user_id,
        provider=provider,
        account_label=label,
        refresh_token_encrypted=b"ciphertext",
    )


def make_document(workspace_id, source_provider=None, source_id=None):
    return Document(
        workspace_id=workspace_id,
        filename="notes.txt",
        file_url=f"workspaces/{workspace_id}/files/notes.txt",
        file_size=7,
        mime_type="text/plain",
        status=DOCUMENT_STATUS_STORED,
        source_provider=source_provider,
        source_id=source_id,
    )


@pytest.mark.asyncio
async def test_a_connection_is_unique_per_user_and_provider(db_session, test_user):
    db_session.add(make_connection(test_user.id))
    await db_session.commit()

    db_session.add(make_connection(test_user.id))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_deleting_a_user_deletes_their_connections(db_session, test_user):
    db_session.add(make_connection(test_user.id))
    await db_session.commit()

    await db_session.execute(delete(type(test_user)).where(type(test_user).id == test_user.id))
    await db_session.commit()

    remaining = await db_session.scalar(select(func.count()).select_from(CloudConnection))
    assert remaining == 0


@pytest.mark.asyncio
async def test_a_document_source_is_unique_per_workspace(db_session, test_workspace):
    db_session.add(make_document(test_workspace.id, "onedrive", "item-1"))
    await db_session.commit()

    db_session.add(make_document(test_workspace.id, "onedrive", "item-1"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_two_documents_with_no_source_coexist(db_session, test_workspace):
    db_session.add(make_document(test_workspace.id))
    db_session.add(make_document(test_workspace.id))

    await db_session.commit()

    count = await db_session.scalar(select(func.count()).select_from(Document))
    assert count == 2


@pytest.mark.asyncio
async def test_the_same_source_id_in_another_workspace_is_allowed(
    db_session, test_workspace, test_user
):
    other = Workspace(name="Other", owner_id=test_user.id)
    db_session.add(other)
    await db_session.commit()

    db_session.add(make_document(test_workspace.id, "google", "file-1"))
    db_session.add(make_document(other.id, "google", "file-1"))

    await db_session.commit()
