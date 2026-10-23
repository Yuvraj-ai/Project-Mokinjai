"""Folder rules become one stored file set, and the API returns it with its source."""

import pytest

from app.models.agent import AgentDocument
from app.models.knowledge import DOCUMENT_STATUS_STORED, Document, FileFolder
from app.models.llm_profile import LlmProfile
from app.models.workspace import Workspace
from app.services.agent_composition import (
    AgentInput,
    CompositionError,
    FolderRule,
    saved_input,
    validate_agent,
)


@pytest.fixture(autouse=True)
def fixed_model_profile(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_capabilities.lookup_profile",
        lambda provider, model_id: {"max_output_tokens": 4096},
    )


def make_profile(workspace_id: str) -> LlmProfile:
    return LlmProfile(
        workspace_id=workspace_id,
        name="Primary",
        provider="openai",
        model_id="gpt-4o-mini",
        encrypted_api_key=b"ciphertext",
        context_window=128000,
        compaction_at_tokens=102400,
        input_price_per_million=0.15,
        output_price_per_million=0.6,
        cache_price_per_million=0.0,
        status="verified",
    )


def agent_input(profile_id: str, **overrides) -> AgentInput:
    base = dict(
        name="Reader",
        description=None,
        llm_profile_id=profile_id,
        system_prompt="Read the files.",
        source_prompt_id=None,
        params={},
        structured_output_id=None,
        web_search=None,
        skill_ids=[],
        tool_ids=[],
        folders=[],
        documents=[],
        connector_ids=[],
        subagent_ids=[],
    )
    base.update(overrides)
    return AgentInput(**base)


async def make_document(db, workspace_id, folder_id, filename):
    document = Document(
        workspace_id=workspace_id,
        folder_id=folder_id,
        filename=filename,
        file_url=f"workspaces/{workspace_id}/files/{filename}",
        file_size=1,
        mime_type="text/plain",
        status=DOCUMENT_STATUS_STORED,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def test_a_folder_rule_expands_to_its_files(db_session, test_workspace):
    profile = make_profile(test_workspace.id)
    folder = FileFolder(workspace_id=test_workspace.id, name="Handbook")
    db_session.add_all([profile, folder])
    await db_session.commit()
    await db_session.refresh(folder)
    first = await make_document(db_session, test_workspace.id, folder.id, "a.txt")
    second = await make_document(db_session, test_workspace.id, folder.id, "b.txt")

    validated = await validate_agent(
        db_session,
        test_workspace.id,
        agent_input(profile.id, folders=[FolderRule(id=folder.id)]),
        agent_id=None,
    )

    assert {row.id for row in validated.attached_documents} == {first.id, second.id}
    assert validated.attachment_sources == {first.id: folder.id, second.id: folder.id}


async def test_an_exclusion_removes_one_file(db_session, test_workspace):
    profile = make_profile(test_workspace.id)
    folder = FileFolder(workspace_id=test_workspace.id, name="Handbook")
    db_session.add_all([profile, folder])
    await db_session.commit()
    await db_session.refresh(folder)
    kept = await make_document(db_session, test_workspace.id, folder.id, "a.txt")
    dropped = await make_document(db_session, test_workspace.id, folder.id, "b.txt")

    validated = await validate_agent(
        db_session,
        test_workspace.id,
        agent_input(
            profile.id,
            folders=[FolderRule(id=folder.id, exclude_document_ids=[dropped.id])],
        ),
        agent_id=None,
    )

    assert [row.id for row in validated.attached_documents] == [kept.id]


async def test_a_direct_document_is_unioned_without_duplication(
    db_session, test_workspace
):
    profile = make_profile(test_workspace.id)
    folder = FileFolder(workspace_id=test_workspace.id, name="Handbook")
    db_session.add_all([profile, folder])
    await db_session.commit()
    await db_session.refresh(folder)
    filed = await make_document(db_session, test_workspace.id, folder.id, "a.txt")
    loose = await make_document(db_session, test_workspace.id, None, "loose.txt")

    validated = await validate_agent(
        db_session,
        test_workspace.id,
        agent_input(
            profile.id,
            folders=[FolderRule(id=folder.id)],
            documents=[filed.id, loose.id],
        ),
        agent_id=None,
    )

    assert {row.id for row in validated.attached_documents} == {filed.id, loose.id}
    assert validated.attachment_sources[filed.id] == folder.id
    assert validated.attachment_sources[loose.id] is None


async def test_a_folder_from_another_workspace_is_rejected(
    db_session, test_workspace, test_user
):
    profile = make_profile(test_workspace.id)
    other = Workspace(name="Other", owner_id=test_user.id)
    db_session.add_all([profile, other])
    await db_session.commit()
    await db_session.refresh(other)
    foreign = FileFolder(workspace_id=other.id, name="Theirs")
    db_session.add(foreign)
    await db_session.commit()

    with pytest.raises(CompositionError) as caught:
        await validate_agent(
            db_session,
            test_workspace.id,
            agent_input(profile.id, folders=[FolderRule(id=foreign.id)]),
            agent_id=None,
        )

    assert [error.field for error in caught.value.errors] == ["folders"]


async def test_a_document_from_another_workspace_is_rejected(
    db_session, test_workspace, test_user
):
    profile = make_profile(test_workspace.id)
    other = Workspace(name="Other", owner_id=test_user.id)
    db_session.add_all([profile, other])
    await db_session.commit()
    await db_session.refresh(other)
    foreign = await make_document(db_session, other.id, None, "theirs.txt")

    with pytest.raises(CompositionError) as caught:
        await validate_agent(
            db_session,
            test_workspace.id,
            agent_input(profile.id, documents=[foreign.id]),
            agent_id=None,
        )

    assert [error.field for error in caught.value.errors] == ["documents"]


async def test_saved_input_reconstructs_documents_from_agent_rows(
    db_session, test_workspace
):
    from app.models.agent import Agent

    profile = make_profile(test_workspace.id)
    folder = FileFolder(workspace_id=test_workspace.id, name="Handbook")
    db_session.add_all([profile, folder])
    await db_session.commit()
    await db_session.refresh(folder)
    document = await make_document(db_session, test_workspace.id, folder.id, "a.txt")
    agent = Agent(
        workspace_id=test_workspace.id,
        name="Reader",
        llm_profile_id=profile.id,
        system_prompt="Read.",
        params={},
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    db_session.add(
        AgentDocument(
            agent_id=agent.id, document_id=document.id, source_folder_id=folder.id
        )
    )
    await db_session.commit()

    data = await saved_input(db_session, agent)

    assert data.documents == [document.id]
    assert data.folders == []


def _payload(profile_id: str, **overrides):
    body = {
        "name": "Reader",
        "description": None,
        "llm_profile_id": profile_id,
        "system_prompt": "Read the files.",
        "params": {},
        "skill_ids": [],
        "tool_ids": [],
        "folders": [],
        "documents": [],
        "connector_ids": [],
        "subagent_ids": [],
    }
    body.update(overrides)
    return body


async def test_create_stores_one_row_per_file_and_get_returns_the_source(
    client, auth_headers, test_workspace, db_session
):
    profile = make_profile(test_workspace.id)
    folder = FileFolder(workspace_id=test_workspace.id, name="Handbook")
    db_session.add_all([profile, folder])
    await db_session.commit()
    await db_session.refresh(folder)
    filed = await make_document(db_session, test_workspace.id, folder.id, "a.txt")
    loose = await make_document(db_session, test_workspace.id, None, "loose.txt")

    created = await client.post(
        f"/api/workspaces/{test_workspace.id}/agents",
        json=_payload(
            profile.id,
            folders=[{"id": folder.id, "exclude_document_ids": []}],
            documents=[filed.id, loose.id],
        ),
        headers=auth_headers,
    )

    assert created.status_code == 201, created.text
    body = created.json()
    assert {row["id"] for row in body["documents"]} == {filed.id, loose.id}
    sources = {row["id"]: row["source_folder_id"] for row in body["documents"]}
    assert sources[filed.id] == folder.id
    assert sources[loose.id] is None
    assert "knowledge_base_ids" not in body


async def test_update_replaces_the_set(
    client, auth_headers, test_workspace, db_session
):
    profile = make_profile(test_workspace.id)
    folder = FileFolder(workspace_id=test_workspace.id, name="Handbook")
    db_session.add_all([profile, folder])
    await db_session.commit()
    await db_session.refresh(folder)
    first = await make_document(db_session, test_workspace.id, folder.id, "a.txt")
    second = await make_document(db_session, test_workspace.id, folder.id, "b.txt")

    created = await client.post(
        f"/api/workspaces/{test_workspace.id}/agents",
        json=_payload(profile.id, folders=[{"id": folder.id, "exclude_document_ids": []}]),
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    agent_id = created.json()["id"]

    updated = await client.put(
        f"/api/workspaces/{test_workspace.id}/agents/{agent_id}",
        json=_payload(
            profile.id,
            folders=[
                {"id": folder.id, "exclude_document_ids": [first.id]}
            ],
        ),
        headers=auth_headers,
    )

    assert updated.status_code == 200, updated.text
    assert [row["id"] for row in updated.json()["documents"]] == [second.id]
