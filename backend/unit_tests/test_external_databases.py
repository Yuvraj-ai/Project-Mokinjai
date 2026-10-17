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


from app.models.workspace import Workspace, WorkspaceMember


def _body(**overrides):
    payload = {
        "name": "Warehouse",
        "kind": "postgres",
        "uri": "postgresql://user:secret@db.example.com:5432/analytics",
        "database_name": "analytics",
    }
    payload.update(overrides)
    return payload


def _collection_url(workspace_id: str) -> str:
    return f"/api/workspaces/{workspace_id}/external-databases"


async def test_create_stores_the_uri_encrypted_and_never_returns_it(
    client, auth_headers, test_workspace, encryption_key, db_session
):
    response = await client.post(
        _collection_url(test_workspace.id), json=_body(), headers=auth_headers
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["has_uri"] is True
    assert body["kind"] == "postgres"
    assert body["database_name"] == "analytics"
    assert "uri" not in body
    assert "encrypted_uri" not in body
    assert "secret" not in response.text

    stored = (
        await db_session.execute(select(ExternalDatabaseConnection))
    ).scalar_one()
    assert stored.encrypted_uri != _body()["uri"].encode()
    assert decrypt_api_key(stored.encrypted_uri) == _body()["uri"]


async def test_the_list_never_contains_a_uri(
    client, auth_headers, test_workspace, encryption_key
):
    await client.post(_collection_url(test_workspace.id), json=_body(), headers=auth_headers)

    listed = await client.get(_collection_url(test_workspace.id), headers=auth_headers)

    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["connections"][0]["has_uri"] is True
    assert "postgresql://" not in listed.text


@pytest.mark.parametrize(
    "overrides",
    [
        {"kind": "sqlite"},
        {"kind": "mysql", "database_name": None},
        {"kind": "postgres", "collection_name": "not-for-postgres"},
        {"kind": "chromadb", "database_name": None, "collection_name": None},
        {"uri": "not-a-uri"},
    ],
)
async def test_invalid_records_are_refused(
    client, auth_headers, test_workspace, encryption_key, overrides
):
    response = await client.post(
        _collection_url(test_workspace.id), json=_body(**overrides), headers=auth_headers
    )

    assert response.status_code == 400, response.text


async def test_a_chromadb_record_uses_the_collection_name(
    client, auth_headers, test_workspace, encryption_key
):
    response = await client.post(
        _collection_url(test_workspace.id),
        json=_body(kind="chromadb", database_name=None, collection_name="handbook"),
        headers=auth_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["collection_name"] == "handbook"
    assert response.json()["database_name"] is None


async def test_get_and_delete_round_trip(client, auth_headers, test_workspace, encryption_key):
    created = await client.post(
        _collection_url(test_workspace.id), json=_body(), headers=auth_headers
    )
    connection_id = created.json()["id"]

    fetched = await client.get(
        f"{_collection_url(test_workspace.id)}/{connection_id}", headers=auth_headers
    )
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == connection_id

    deleted = await client.delete(
        f"{_collection_url(test_workspace.id)}/{connection_id}", headers=auth_headers
    )
    assert deleted.status_code == 200, deleted.text

    gone = await client.get(
        f"{_collection_url(test_workspace.id)}/{connection_id}", headers=auth_headers
    )
    assert gone.status_code == 404, gone.text


async def test_patch_with_a_blank_uri_keeps_the_ciphertext(
    client, auth_headers, test_workspace, encryption_key, db_session
):
    """The blank-secret rule, copied from the LLM-profile retest path.

    A secret that can never be read back cannot be edited by echo, so an empty value
    must mean "leave it".
    """
    created = await client.post(
        _collection_url(test_workspace.id), json=_body(), headers=auth_headers
    )
    connection_id = created.json()["id"]
    before = (
        await db_session.execute(select(ExternalDatabaseConnection))
    ).scalar_one().encrypted_uri

    response = await client.patch(
        f"{_collection_url(test_workspace.id)}/{connection_id}",
        json={"name": "Renamed", "uri": ""},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Renamed"

    db_session.expire_all()
    after = (
        await db_session.execute(select(ExternalDatabaseConnection))
    ).scalar_one().encrypted_uri
    assert after == before, "a blank URI must keep the stored ciphertext"


async def test_a_connection_in_another_workspace_is_not_visible(
    client, auth_headers, test_workspace, test_user, encryption_key, db_session
):
    """The user is a member of both workspaces, so this tests scoping, not RBAC."""
    other = Workspace(name="Other Workspace", owner_id=test_user.id)
    db_session.add(other)
    await db_session.commit()
    db_session.add(
        WorkspaceMember(workspace_id=other.id, user_id=test_user.id, role="owner")
    )
    await db_session.commit()

    created = await client.post(
        _collection_url(test_workspace.id), json=_body(), headers=auth_headers
    )

    response = await client.get(
        f"{_collection_url(other.id)}/{created.json()['id']}", headers=auth_headers
    )

    assert response.status_code == 404, response.text
