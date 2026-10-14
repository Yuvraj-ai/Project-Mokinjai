"""Structured output API.

The service tests cover compilation and parsing; these cover the HTTP contract:
persistence, reference-aware delete and rename, and who is allowed to do what.
"""

import json

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.structured_output import StructuredOutput
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.utils.security import create_access_token, hash_password


def url(workspace_id: str) -> str:
    return f"/api/workspaces/{workspace_id}/structured-outputs"


def field(name, type_, description="What goes here.", required=True, **extra):
    return {"name": name, "type": type_, "description": description, "required": required, **extra}


def payload(name="MathReasoning", description="Reasoning steps, then the answer.", fields=None):
    return {
        "name": name,
        "description": description,
        "fields": fields or [field("answer", "string", "The final answer.")],
    }


def headers_for(user: User) -> dict[str, str]:
    token = create_access_token({"sub": user.id, "email": user.email})
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
    output_id = body["id"]
    assert body["name"] == "MathReasoning"
    assert body["compiled_schema"]["title"] == "MathReasoning"

    listed = await client.get(base, headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    fetched = await client.get(f"{base}/{output_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["compiled_schema"]["properties"]["answer"]["type"] == "string"

    updated = await client.put(
        f"{base}/{output_id}",
        json=payload(description="Now with two fields", fields=[field("answer", "string")]),
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Now with two fields"

    deleted = await client.delete(f"{base}/{output_id}", headers=auth_headers)
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
        "fields",
        "referenced_by",
        "compiled_schema",
        "created_at",
        "updated_at",
    }


@pytest.mark.asyncio
async def test_list_field_round_trips_through_storage(client, db_session, test_workspace, auth_headers):
    step = await client.post(
        url(test_workspace.id), json=payload("Step", fields=[field("text", "string")]), headers=auth_headers
    )
    assert step.status_code == 200

    created = await client.post(
        url(test_workspace.id),
        json=payload(
            "Plan",
            fields=[
                field("steps", "list", "Ordered steps.", items_type="reference", items_ref="Step"),
                field("tags", "list", "Labels.", items_type="string"),
            ],
        ),
        headers=auth_headers,
    )
    assert created.status_code == 200, created.text
    returned = created.json()["fields"]
    assert returned[0]["items_type"] == "reference"
    assert returned[0]["items_ref"] == "Step"
    assert returned[1]["items_type"] == "string"
    assert set(created.json()["compiled_schema"]["$defs"]) == {"Step"}

    # Type-invalid keys are absent from the stored JSON, not written as null.
    # (The response model still serializes them, which the frontend types allow.)
    row = (
        await db_session.execute(
            select(StructuredOutput).where(StructuredOutput.id == created.json()["id"])
        )
    ).scalar_one()
    assert row.fields[0]["items_ref"] == "Step"
    assert "items_ref" not in row.fields[1]
    assert "ref" not in row.fields[1]


@pytest.mark.asyncio
async def test_duplicate_name_is_rejected_ignoring_case(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    assert (await client.post(base, json=payload("MathReasoning"), headers=auth_headers)).status_code == 200

    clash = await client.post(base, json=payload("mathreasoning"), headers=auth_headers)
    assert clash.status_code == 409


@pytest.mark.asyncio
async def test_the_same_name_is_allowed_in_another_workspace(
    client, test_workspace, second_workspace, auth_headers
):
    assert (
        await client.post(url(test_workspace.id), json=payload("MathReasoning"), headers=auth_headers)
    ).status_code == 200
    other = await client.post(url(second_workspace.id), json=payload("MathReasoning"), headers=auth_headers)
    assert other.status_code == 200


@pytest.mark.asyncio
async def test_delete_is_blocked_while_referenced(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    step = (await client.post(base, json=payload("Step", fields=[field("text", "string")]), headers=auth_headers)).json()
    await client.post(
        base,
        json=payload("MathReasoning", fields=[field("step", "reference", ref="Step")]),
        headers=auth_headers,
    )

    blocked = await client.delete(f"{base}/{step['id']}", headers=auth_headers)
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == (
        "Cannot delete: referenced by MathReasoning. Remove the reference first."
    )

    listed = await client.get(base, headers=auth_headers)
    step_item = next(item for item in listed.json()["structured_outputs"] if item["name"] == "Step")
    assert step_item["referenced_by"] == ["MathReasoning"]


@pytest.mark.asyncio
async def test_rename_cascades_into_referring_definitions(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    step = (await client.post(base, json=payload("Step", fields=[field("text", "string")]), headers=auth_headers)).json()
    plan = (
        await client.post(
            base,
            json=payload(
                "MathReasoning",
                fields=[field("steps", "list", items_type="reference", items_ref="Step")],
            ),
            headers=auth_headers,
        )
    ).json()
    assert set(plan["compiled_schema"]["$defs"]) == {"Step"}

    renamed = await client.put(
        f"{base}/{step['id']}",
        json=payload("SolutionStep", fields=[field("text", "string")]),
        headers=auth_headers,
    )
    assert renamed.status_code == 200, renamed.text

    after = await client.get(f"{base}/{plan['id']}", headers=auth_headers)
    assert after.status_code == 200
    compiled = after.json()["compiled_schema"]
    assert set(compiled["$defs"]) == {"SolutionStep"}
    assert compiled["properties"]["steps"]["items"] == {"$ref": "#/$defs/SolutionStep"}


@pytest.mark.asyncio
async def test_unresolved_reference_is_rejected_on_create(client, test_workspace, auth_headers):
    response = await client.post(
        url(test_workspace.id),
        json=payload("Plan", fields=[field("step", "reference", ref="Ghost")]),
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Ghost" in response.json()["detail"]


@pytest.mark.asyncio
async def test_a_cycle_is_rejected(client, test_workspace, auth_headers):
    """Step can reference MathReasoning only if MathReasoning does not reach back."""
    base = url(test_workspace.id)
    step = (await client.post(base, json=payload("Step", fields=[field("text", "string")]), headers=auth_headers)).json()
    plan = await client.post(
        base,
        json=payload("MathReasoning", fields=[field("step", "reference", ref="Step")]),
        headers=auth_headers,
    )
    assert plan.status_code == 200

    closing = await client.put(
        f"{base}/{step['id']}",
        json=payload("Step", fields=[field("back", "reference", ref="MathReasoning")]),
        headers=auth_headers,
    )
    assert closing.status_code == 400
    assert "Circular reference" in closing.json()["detail"]


@pytest.mark.asyncio
async def test_unknown_id_is_not_found(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    assert (await client.get(f"{base}/nope", headers=auth_headers)).status_code == 404
    assert (await client.put(f"{base}/nope", json=payload(), headers=auth_headers)).status_code == 404
    assert (await client.delete(f"{base}/nope", headers=auth_headers)).status_code == 404


@pytest.mark.asyncio
async def test_a_definition_in_another_workspace_is_not_visible(
    client, test_workspace, second_workspace, auth_headers
):
    other = (
        await client.post(url(second_workspace.id), json=payload(), headers=auth_headers)
    ).json()
    assert (await client.get(f"{url(test_workspace.id)}/{other['id']}", headers=auth_headers)).status_code == 404


@pytest.mark.asyncio
async def test_viewer_can_read_but_not_write(client, db_session, test_workspace, viewer_user, auth_headers):
    base = url(test_workspace.id)
    assert (await client.post(base, json=payload(), headers=auth_headers)).status_code == 200

    db_session.add(
        WorkspaceMember(workspace_id=test_workspace.id, user_id=viewer_user.id, role="viewer")
    )
    await db_session.commit()
    viewer_headers = headers_for(viewer_user)

    assert (await client.get(base, headers=viewer_headers)).status_code == 200
    assert (await client.post(base, json=payload("Other"), headers=viewer_headers)).status_code == 403


@pytest.mark.asyncio
async def test_editor_can_write(client, db_session, test_workspace, viewer_user):
    db_session.add(
        WorkspaceMember(workspace_id=test_workspace.id, user_id=viewer_user.id, role="editor")
    )
    await db_session.commit()

    response = await client.post(
        url(test_workspace.id), json=payload(), headers=headers_for(viewer_user)
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_parse_schema_converts_without_saving(client, test_workspace, auth_headers):
    base = url(test_workspace.id)
    await client.post(base, json=payload("Step", fields=[field("text", "string")]), headers=auth_headers)

    raw = json.dumps(
        {
            "title": "MathReasoning",
            "description": "Reasoning steps, then the answer.",
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/Step"},
                    "description": "Ordered steps.",
                }
            },
            "required": ["steps"],
        }
    )
    parsed = await client.post(f"{base}/parse-schema", json={"schema": raw}, headers=auth_headers)
    assert parsed.status_code == 200, parsed.text
    body = parsed.json()
    assert body["title"] == "MathReasoning"
    assert body["fields"][0]["items_ref"] == "Step"

    assert (await client.get(base, headers=auth_headers)).json()["total"] == 1


@pytest.mark.asyncio
async def test_parse_schema_reports_the_offending_keyword(client, test_workspace, auth_headers):
    raw = json.dumps(
        {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "enum": ["a", "b"], "description": "The answer."}
            },
        }
    )
    response = await client.post(
        f"{url(test_workspace.id)}/parse-schema", json={"schema": raw}, headers=auth_headers
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "enum" in detail
    assert "answer" in detail
