"""The tools API.

The extraction rules are covered by `test_tool_schema.py` and the registry by
`test_builtin_tools.py`; these cover the HTTP contract: what a write stores, what a
read derives, and who is allowed to do what.
"""

import pytest_asyncio

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.utils.security import create_access_token, hash_password


def url(workspace_id: str) -> str:
    return f"/api/workspaces/{workspace_id}/tools"


WEATHER = '''
def get_weather(city: str, units: str = "metric") -> str:
    """Report the weather for a city.

    Args:
        city: The city to report on, e.g. Lisbon.
        units: Either "metric" or "imperial".
    """
    return f"{city}: 18 degrees ({units})"
'''


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


async def test_a_new_workspace_has_no_tools(client, test_workspace, auth_headers):
    response = await client.get(url(test_workspace.id), headers=auth_headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"tools": [], "total": 0}


async def test_builtin_tools_are_listed_without_their_source(client, test_workspace, auth_headers):
    response = await client.get(f"{url(test_workspace.id)}/builtin", headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert {"current_time", "word_count"} <= {item["built_in_key"] for item in body["tools"]}

    current_time = next(
        item for item in body["tools"] if item["built_in_key"] == "current_time"
    )
    assert current_time["name"] == "Current Time"
    assert current_time["description"] == "Return the current time in a named timezone."
    assert current_time["category"] == "built-in"
    assert current_time["needs_sandbox"] is False
    assert set(current_time) == {
        "built_in_key",
        "name",
        "description",
        "category",
        "needs_sandbox",
    }, "ADR-015: a built-in's name and description, and nothing else"


async def test_the_builtin_route_is_not_read_as_a_tool_id(client, test_workspace, auth_headers):
    """`/builtin` is declared before `/{tool_id}`; this is what that ordering buys."""
    response = await client.get(f"{url(test_workspace.id)}/builtin", headers=auth_headers)

    assert response.status_code == 200
    assert "tools" in response.json()


async def test_a_viewer_can_read_the_builtin_list(client, db_session, test_workspace, viewer_user):
    db_session.add(
        WorkspaceMember(workspace_id=test_workspace.id, user_id=viewer_user.id, role="viewer")
    )
    await db_session.commit()

    response = await client.get(
        f"{url(test_workspace.id)}/builtin", headers=await headers_for(db_session, viewer_user)
    )

    assert response.status_code == 200, response.text


async def test_validate_returns_the_extracted_schema(client, test_workspace, auth_headers):
    response = await client.post(
        f"{url(test_workspace.id)}/validate", json={"code": WEATHER}, headers=auth_headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is True
    assert body["errors"] == []
    assert body["schema"]["name"] == "get_weather"
    assert body["schema"]["description"] == "Report the weather for a city."
    assert body["schema"]["input_schema"]["required"] == ["city"]
    assert body["schema"]["input_schema"]["properties"]["units"]["type"] == "string"
    assert body["schema"]["returns"] == "string"


async def test_validate_stores_nothing(client, test_workspace, auth_headers):
    base = url(test_workspace.id)

    previewed = await client.post(
        f"{base}/validate", json={"code": WEATHER}, headers=auth_headers
    )
    assert previewed.status_code == 200

    assert (await client.get(base, headers=auth_headers)).json() == {"tools": [], "total": 0}


async def test_validate_reports_what_is_missing_as_data(client, test_workspace, auth_headers):
    """Half-typed code is the normal case, so this is 200 with the errors in the body."""
    response = await client.post(
        f"{url(test_workspace.id)}/validate",
        json={"code": "def half_typed(value: str) -> str:\n    return value\n"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is False
    assert body["schema"] is None
    assert any("no docstring" in error for error in body["errors"]), body["errors"]


async def test_validate_requires_an_editor(client, db_session, test_workspace, viewer_user):
    db_session.add(
        WorkspaceMember(workspace_id=test_workspace.id, user_id=viewer_user.id, role="viewer")
    )
    await db_session.commit()

    response = await client.post(
        f"{url(test_workspace.id)}/validate",
        json={"code": WEATHER},
        headers=await headers_for(db_session, viewer_user),
    )

    assert response.status_code == 403, response.text


async def test_validate_rejects_an_empty_body(client, test_workspace, auth_headers):
    response = await client.post(
        f"{url(test_workspace.id)}/validate", json={"code": ""}, headers=auth_headers
    )

    assert response.status_code == 422
