"""Skill API.

The service tests cover parsing, validation and compilation; these cover the HTTP
contract: persistence, reference-aware delete and rename, the reference menu, and
who is allowed to do what.

The tests that need a tool to exist import `app.models.tool.Tool`, which the Tools
feature provides. `/ToolName` validation and the `/` half of the reference menu
are therefore live.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.skill import Skill
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.utils.security import create_access_token, hash_password


def url(workspace_id: str) -> str:
    return f"/api/workspaces/{workspace_id}/skills"


def payload(name="Writer", description="Sets the tone.", content="Do the thing."):
    return {"name": name, "description": description, "content": content}


async def headers_for(db, user: User) -> dict[str, str]:
    """A token for a user, backed by a real session.

    The middleware validates the session behind a token's `sid`, so a token minted
    without one is rejected. This mirrors the `auth_headers` fixture.
    """
    from app.services.sessions import create_session, new_refresh_token

    session = await create_session(db, user_id=user.id, refresh_token=new_refresh_token())
    token = create_access_token({"sub": user.id, "email": user.email, "sid": session.id})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def viewer_user(db_session):
    user = User(
        email="viewer@example.com",
        hashed_password=hash_password("viewerpass123"),
        name="Viewer User",
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def second_workspace(db_session, test_user):
    workspace = Workspace(name="Second Workspace", owner_id=test_user.id)
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    db_session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=test_user.id, role="owner")
    )
    await db_session.commit()
    return workspace


@pytest.mark.asyncio
async def test_round_trip(client, test_workspace, auth_headers):
    base = url(test_workspace.id)

    created = await client.post(base, json=payload(), headers=auth_headers)
    assert created.status_code == 200, created.text
    body = created.json()
    skill_id = body["id"]
    assert body["name"] == "Writer"
    assert body["skill_refs"] == []
    assert body["referenced_by"] == []

    listed = await client.get(base, headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    fetched = await client.get(f"{base}/{skill_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["content"] == "Do the thing."

    updated = await client.put(
        f"{base}/{skill_id}",
        json=payload(description="Now for technical writing.", content="Call /current_time."),
        headers=auth_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["description"] == "Now for technical writing."
    assert updated.json()["tool_refs"] == ["current_time"]

    deleted = await client.delete(f"{base}/{skill_id}", headers=auth_headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"success": True}

    assert (await client.get(base, headers=auth_headers)).json()["total"] == 0


@pytest.mark.asyncio
async def test_response_exposes_exactly_the_declared_keys(client, test_workspace, auth_headers):
    created = await client.post(url(test_workspace.id), json=payload(), headers=auth_headers)

    assert set(created.json().keys()) == {
        "id",
        "workspace_id",
        "name",
        "description",
        "content",
        "skill_refs",
        "tool_refs",
        "referenced_by",
        "created_at",
        "updated_at",
    }


@pytest.mark.asyncio
async def test_the_parsed_references_come_back_in_the_response(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    await client.post(base, json=payload("Step", content="A step."), headers=auth_headers)

    created = await client.post(
        base,
        json=payload(
            "Writer",
            content="Follow @Step.\n\n```\n@Ghost is an example\n```\n",
        ),
        headers=auth_headers,
    )

    assert created.status_code == 200, created.text
    assert created.json()["skill_refs"] == ["Step"]


@pytest.mark.asyncio
async def test_a_duplicate_name_is_rejected_ignoring_case(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    assert (await client.post(base, json=payload("Writer"), headers=auth_headers)).status_code == 200

    clash = await client.post(base, json=payload("writer"), headers=auth_headers)

    assert clash.status_code == 409


@pytest.mark.asyncio
async def test_the_same_name_is_allowed_in_another_workspace(
    client, test_workspace, second_workspace, auth_headers
):
    assert (
        await client.post(url(test_workspace.id), json=payload("Writer"), headers=auth_headers)
    ).status_code == 200

    other = await client.post(url(second_workspace.id), json=payload("Writer"), headers=auth_headers)

    assert other.status_code == 200


@pytest.mark.asyncio
async def test_an_unresolved_skill_reference_is_rejected_on_create(
    client, test_workspace, auth_headers
):
    response = await client.post(
        url(test_workspace.id), json=payload("Writer", content="Use @Ghost."), headers=auth_headers
    )

    assert response.status_code == 400
    assert "Ghost" in response.json()["detail"]


@pytest.mark.asyncio
async def test_a_cycle_is_rejected(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    alpha = (await client.post(base, json=payload("Alpha", content="Plain."), headers=auth_headers)).json()
    await client.post(
        base, json=payload("Beta", content="Then @Alpha."), headers=auth_headers
    )

    closing = await client.put(
        f"{base}/{alpha['id']}", json=payload("Alpha", content="Then @Beta."), headers=auth_headers
    )

    assert closing.status_code == 400
    assert "Circular reference" in closing.json()["detail"]
    assert "→" in closing.json()["detail"]


@pytest.mark.asyncio
async def test_a_self_reference_is_rejected(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    created = (await client.post(base, json=payload("Loop", content="Plain."), headers=auth_headers)).json()

    response = await client.put(
        f"{base}/{created['id']}", json=payload("Loop", content="Then @Loop."), headers=auth_headers
    )

    assert response.status_code == 400
    assert "Circular reference" in response.json()["detail"]


@pytest.mark.asyncio
async def test_a_missing_description_is_rejected(client, test_workspace, auth_headers):
    response = await client.post(
        url(test_workspace.id), json=payload("Writer", description=""), headers=auth_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_name_that_cannot_be_referenced_is_rejected(client, test_workspace, auth_headers):
    response = await client.post(
        url(test_workspace.id), json=payload("not a name"), headers=auth_headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_is_blocked_while_referenced(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    step = (await client.post(base, json=payload("Step", content="A step."), headers=auth_headers)).json()
    await client.post(
        base, json=payload("Writer", content="Follow @Step."), headers=auth_headers
    )

    blocked = await client.delete(f"{base}/{step['id']}", headers=auth_headers)

    assert blocked.status_code == 409
    assert blocked.json()["detail"] == (
        "Cannot delete: referenced by Writer. Remove the reference first."
    )

    listed = await client.get(base, headers=auth_headers)
    item = next(entry for entry in listed.json()["skills"] if entry["name"] == "Step")
    assert item["referenced_by"] == ["Writer"]


@pytest.mark.asyncio
async def test_rename_cascades_into_referring_skills(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    step = (await client.post(base, json=payload("Step", content="A step."), headers=auth_headers)).json()
    writer = (
        await client.post(base, json=payload("Writer", content="Follow @Step."), headers=auth_headers)
    ).json()

    renamed = await client.put(
        f"{base}/{step['id']}",
        json=payload("SolutionStep", content="A step."),
        headers=auth_headers,
    )
    assert renamed.status_code == 200, renamed.text

    after = await client.get(f"{base}/{writer['id']}", headers=auth_headers)
    assert after.json()["content"] == "Follow @SolutionStep."
    assert after.json()["skill_refs"] == ["SolutionStep"]


@pytest.mark.asyncio
async def test_rename_leaves_a_fenced_example_alone(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    step = (await client.post(base, json=payload("Step", content="A step."), headers=auth_headers)).json()
    writer = (
        await client.post(
            base,
            json=payload("Writer", content="Follow @Step.\n\n```\n@Step in a sample\n```\n"),
            headers=auth_headers,
        )
    ).json()

    await client.put(
        f"{base}/{step['id']}",
        json=payload("SolutionStep", content="A step."),
        headers=auth_headers,
    )

    after = await client.get(f"{base}/{writer['id']}", headers=auth_headers)
    assert after.json()["content"] == "Follow @SolutionStep.\n\n```\n@Step in a sample\n```\n"


@pytest.mark.asyncio
async def test_unknown_id_is_not_found(client, test_workspace, auth_headers):
    base = url(test_workspace.id)

    assert (await client.get(f"{base}/nope", headers=auth_headers)).status_code == 404
    assert (await client.put(f"{base}/nope", json=payload(), headers=auth_headers)).status_code == 404
    assert (await client.delete(f"{base}/nope", headers=auth_headers)).status_code == 404


@pytest.mark.asyncio
async def test_a_skill_in_another_workspace_is_not_visible(
    client, test_workspace, second_workspace, auth_headers
):
    other = (
        await client.post(url(second_workspace.id), json=payload(), headers=auth_headers)
    ).json()

    assert (
        await client.get(f"{url(test_workspace.id)}/{other['id']}", headers=auth_headers)
    ).status_code == 404


@pytest.mark.asyncio
async def test_the_reference_menu_lists_skills(
    client, test_workspace, auth_headers
):
    await client.post(
        url(test_workspace.id),
        json=payload("Writer", description="Sets the tone."),
        headers=auth_headers,
    )

    menu = await client.get(f"{url(test_workspace.id)}/reference-menu", headers=auth_headers)

    assert menu.status_code == 200, menu.text
    assert menu.json()["skills"] == [{"name": "Writer", "description": "Sets the tone."}]

    # Built-ins are merged into the tools half, so a workspace with no tools of
    # its own still lists them. Asserted against the registry, not a fixed list.
    from app.tools import list_builtin_tools

    assert [entry["name"] for entry in menu.json()["tools"]] == [
        entry.key for entry in list_builtin_tools()
    ]


@pytest.mark.asyncio
async def test_viewer_can_read_but_not_write(client, db_session, test_workspace, viewer_user, auth_headers):
    base = url(test_workspace.id)
    assert (await client.post(base, json=payload(), headers=auth_headers)).status_code == 200

    db_session.add(
        WorkspaceMember(workspace_id=test_workspace.id, user_id=viewer_user.id, role="viewer")
    )
    await db_session.commit()
    viewer_headers = await headers_for(db_session, viewer_user)

    assert (await client.get(base, headers=viewer_headers)).status_code == 200
    assert (await client.post(base, json=payload("Other"), headers=viewer_headers)).status_code == 403


@pytest.mark.asyncio
async def test_editor_can_write(client, db_session, test_workspace, viewer_user):
    db_session.add(
        WorkspaceMember(workspace_id=test_workspace.id, user_id=viewer_user.id, role="editor")
    )
    await db_session.commit()

    response = await client.post(
        url(test_workspace.id), json=payload(), headers=await headers_for(db_session, viewer_user)
    )

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_a_non_member_gets_not_found(client, db_session, test_workspace, viewer_user):
    response = await client.get(
        url(test_workspace.id), headers=await headers_for(db_session, viewer_user)
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_an_unresolved_tool_reference_is_rejected(client, db_session, test_workspace, auth_headers):
    """Needs a `tools` row to exercise `/ToolName` validation."""
    from app.models.tool import Tool

    db_session.add(
        Tool(
            workspace_id=test_workspace.id,
            name="SearchWeb",
            # `tools` stores `code` as canonical and derives everything else on
            # read (Tools spec §1, §3): there is no `description` column, and
            # `code` is NOT NULL, so the fixture must supply real source.
            code=(
                "def SearchWeb(query: str) -> str:\n"
                '    """Search the web.\n'
                "\n"
                "    Args:\n"
                "        query: What to look for.\n"
                '    """\n'
            ),
        )
    )
    await db_session.commit()

    base = url(test_workspace.id)

    missing = await client.post(
        base, json=payload("Writer", content="Call /Ghost."), headers=auth_headers
    )
    assert missing.status_code == 400
    assert "Ghost" in missing.json()["detail"]

    found = await client.post(
        base, json=payload("Writer", content="Call /SearchWeb."), headers=auth_headers
    )
    assert found.status_code == 200, found.text


@pytest.mark.asyncio
async def test_the_reference_menu_lists_tools(client, db_session, test_workspace, auth_headers):
    """Needs a `tools` row to exercise the `/` half of the reference menu."""
    from app.models.tool import Tool

    db_session.add(
        Tool(
            workspace_id=test_workspace.id,
            name="SearchWeb",
            # `tools` stores `code` as canonical and derives everything else on
            # read (Tools spec §1, §3): there is no `description` column, and
            # `code` is NOT NULL, so the fixture must supply real source.
            code=(
                "def SearchWeb(query: str) -> str:\n"
                '    """Search the web.\n'
                "\n"
                "    Args:\n"
                "        query: What to look for.\n"
                '    """\n'
            ),
        )
    )
    await db_session.commit()

    menu = await client.get(f"{url(test_workspace.id)}/reference-menu", headers=auth_headers)

    assert menu.status_code == 200, menu.text

    by_name = {entry["name"]: entry["description"] for entry in menu.json()["tools"]}

    # The description is derived from the tool's code, not read from a column.
    assert by_name["SearchWeb"] == "Search the web."

    # Built-ins are referenceable by key and appear in the same menu (Tools spec,
    # "Owed to other plans", item 2). Asserted against the registry rather than a
    # hard-coded list, so growing the built-in set cannot make this test a lie.
    from app.tools import list_builtin_tools

    for entry in list_builtin_tools():
        assert by_name[entry.key] == entry.schema.description
