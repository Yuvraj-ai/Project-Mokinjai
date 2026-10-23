"""The file-library tables: workspace scoping, root files, and delete guards."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.agent import Agent, AgentDocument
from app.models.knowledge import DOCUMENT_STATUS_STORED, Document, FileFolder


async def make_folder(db, workspace_id, name="Docs"):
    folder = FileFolder(workspace_id=workspace_id, name=name)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def make_document(db, workspace_id, folder_id=None, filename="notes.txt"):
    document = Document(
        workspace_id=workspace_id,
        folder_id=folder_id,
        filename=filename,
        file_url=f"workspaces/{workspace_id}/files/{filename}",
        file_size=7,
        mime_type="text/plain",
        status=DOCUMENT_STATUS_STORED,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def make_agent(db, workspace_id, name="Reader"):
    agent = Agent(
        workspace_id=workspace_id,
        name=name,
        system_prompt="Read the files.",
        params={},
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@pytest.mark.asyncio
async def test_a_root_document_belongs_to_a_workspace(db_session, test_workspace):
    document = await make_document(db_session, test_workspace.id)

    assert document.folder_id is None
    assert document.workspace_id == test_workspace.id


@pytest.mark.asyncio
async def test_a_folder_lists_its_documents(db_session, test_workspace):
    folder = await make_folder(db_session, test_workspace.id)
    filed = await make_document(db_session, test_workspace.id, folder.id, "filed.txt")
    root = await make_document(db_session, test_workspace.id, None, "root.txt")

    loaded = await db_session.get(FileFolder, folder.id)
    await db_session.refresh(loaded, ["documents"])

    assert [row.id for row in loaded.documents] == [filed.id]
    assert root.id != filed.id


@pytest.mark.asyncio
async def test_deleting_a_folder_with_documents_is_restricted(
    db_session, session_factory, test_workspace
):
    folder = await make_folder(db_session, test_workspace.id)
    document = await make_document(db_session, test_workspace.id, folder.id)
    document_id = document.id

    with pytest.raises(IntegrityError):
        await db_session.delete(folder)
        await db_session.commit()

    await db_session.rollback()
    async with session_factory() as fresh:
        assert await fresh.get(Document, document_id) is not None


@pytest.mark.asyncio
async def test_deleting_an_attached_document_is_restricted(
    db_session, session_factory, test_workspace
):
    folder = await make_folder(db_session, test_workspace.id)
    document = await make_document(db_session, test_workspace.id, folder.id)
    agent = await make_agent(db_session, test_workspace.id)
    document_id = document.id

    db_session.add(
        AgentDocument(agent_id=agent.id, document_id=document_id, source_folder_id=folder.id)
    )
    await db_session.commit()

    with pytest.raises(IntegrityError):
        await db_session.delete(document)
        await db_session.commit()

    await db_session.rollback()
    async with session_factory() as fresh:
        assert await fresh.get(Document, document_id) is not None


@pytest.mark.asyncio
async def test_agent_documents_are_unique_per_agent_and_document(
    db_session, test_workspace
):
    folder = await make_folder(db_session, test_workspace.id)
    document = await make_document(db_session, test_workspace.id, folder.id)
    agent = await make_agent(db_session, test_workspace.id)

    db_session.add(AgentDocument(agent_id=agent.id, document_id=document.id))
    await db_session.commit()

    with pytest.raises(IntegrityError):
        db_session.add(AgentDocument(agent_id=agent.id, document_id=document.id))
        await db_session.commit()
