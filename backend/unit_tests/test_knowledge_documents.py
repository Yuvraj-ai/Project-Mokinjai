"""Knowledge Base documents: the type narrowing, the document contract, and the seams.

What this file does not test is text extraction or retrieval — neither exists, and
neither is this feature's. `test_the_documents_table_carries_no_vector_machinery` is the
guard that keeps that true while the vector design is still pending.
"""

import pytest
from sqlalchemy import text


def _kb_body(**overrides):
    payload = {"name": "Handbook", "description": "Company docs"}
    payload.update(overrides)
    return payload


def _kb_url(workspace_id: str) -> str:
    return f"/api/workspaces/{workspace_id}/knowledge-bases"


async def test_creating_a_document_knowledge_base_succeeds(
    client, auth_headers, test_workspace
):
    response = await client.post(
        _kb_url(test_workspace.id), json=_kb_body(type="document"), headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["type"] == "document"


async def test_the_default_type_is_document(client, auth_headers, test_workspace):
    response = await client.post(
        _kb_url(test_workspace.id), json=_kb_body(), headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["type"] == "document"


@pytest.mark.parametrize("kb_type", ["url", "api", "anything"])
async def test_an_unsupported_type_is_refused(
    client, auth_headers, test_workspace, kb_type
):
    """`url` and `api` are refused, not accepted-and-ignored.

    Neither has a design: a url knowledge base implies fetching and crawling, and an api
    knowledge base is undefined altogether. Storing a row nothing can act on is a lie the
    UI would have to repeat.
    """
    response = await client.post(
        _kb_url(test_workspace.id), json=_kb_body(type=kb_type), headers=auth_headers
    )

    assert response.status_code == 400, response.text
    assert kb_type in response.json()["detail"]


async def test_the_documents_table_carries_no_vector_machinery(db_session):
    """The deferral, pinned at the table level.

    `test_schema_types.py` pins `vector_ids` to `text`. This pins the whole column set, so
    an embedding column, a dimension constant or an `ARRAY` cannot arrive before the
    vector design lands and the `vector_ids` question is answered.
    """
    rows = await db_session.execute(
        text(
            "select column_name from information_schema.columns "
            "where table_schema = 'public' and table_name = 'documents'"
        )
    )

    assert {row[0] for row in rows} == {
        "id",
        "knowledge_base_id",
        "filename",
        "file_url",
        "file_size",
        "mime_type",
        "content",
        "metadata",
        "vector_ids",
        "status",
        "created_at",
        "updated_at",
    }


def test_the_status_vocabulary_is_the_decided_set():
    from app.models.knowledge import (
        DOCUMENT_STATUS_FAILED,
        DOCUMENT_STATUS_INDEXED,
        DOCUMENT_STATUS_STORED,
        DOCUMENT_STATUSES,
    )

    assert DOCUMENT_STATUSES == ("stored", "indexed", "failed")
    assert DOCUMENT_STATUS_STORED == "stored"
    assert DOCUMENT_STATUS_INDEXED == "indexed"
    assert DOCUMENT_STATUS_FAILED == "failed"
