"""External database connection records (ADR-012).

A record is a URI plus its target names, scoped to a workspace. The URI is a credential:
Fernet-encrypted at rest and never returned by any endpoint. A record is not a
connection — creating one contacts nothing, and no driver is imported for any kind.
"""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.config import get_settings
from app.crypto import decrypt_api_key, encrypt_api_key
from app.models.external_database import KINDS, ExternalDatabaseConnection


@pytest.fixture
def encryption_key():
    """Same shape as test_llm_profiles.py:14-20 — the Fernet key is an environment fact.

    crypto.py raises RuntimeError when LLM_ENCRYPTION_KEY is blank, so a test that
    encrypts anything must supply one rather than depend on the machine's `.env`.
    """
    settings = get_settings()
    previous = settings.LLM_ENCRYPTION_KEY
    settings.LLM_ENCRYPTION_KEY = Fernet.generate_key().decode()
    yield settings.LLM_ENCRYPTION_KEY
    settings.LLM_ENCRYPTION_KEY = previous


def test_the_four_supported_kinds_are_named():
    assert KINDS == ("postgres", "mysql", "mongodb", "chromadb")


async def test_a_connection_persists_and_round_trips(db_session, test_workspace, encryption_key):
    db_session.add(
        ExternalDatabaseConnection(
            workspace_id=test_workspace.id,
            name="Warehouse",
            kind="postgres",
            encrypted_uri=encrypt_api_key("postgresql://user:secret@db.example.com:5432/analytics"),
            database_name="analytics",
        )
    )
    await db_session.commit()

    found = (
        await db_session.execute(
            select(ExternalDatabaseConnection).where(
                ExternalDatabaseConnection.name == "Warehouse"
            )
        )
    ).scalar_one()

    assert found.workspace_id == test_workspace.id
    assert found.kind == "postgres"
    assert found.database_name == "analytics"
    assert found.collection_name is None
    assert decrypt_api_key(found.encrypted_uri).startswith("postgresql://")
    assert found.created_at is not None, "created_at should come from the server default"
    assert found.updated_at is not None, "updated_at should come from the server default"
