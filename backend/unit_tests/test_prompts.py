"""Prompt library API.

The prompts router had no tests at all, and the one piece of it worth pinning
down is the token count the editor displays. It is a computed field, evaluated
on read against tiktoken's o200k_base encoding and never stored, so these tests
assert against known-good counts instead of re-deriving them with the function
under test.
"""

import pytest

from app.models.prompt import PromptTemplate


# Ground truth from tiktoken's o200k_base encoding. LONG is deliberately a
# string that cl100k_base scores differently (14), so swapping the encoding
# fails a test rather than quietly shifting every count in the UI.
HELPFUL = "You are a helpful assistant."  # 6
LONG = "Explain the difference between a process and a thread in three sentences."  # 13
TEMPLATED = "Summarize the following document in {n} bullet points:\n\n{document}"  # 16


def url(workspace_id: str) -> str:
    return f"/api/workspaces/{workspace_id}/prompts"


async def test_create_prompt_returns_token_count(client, auth_headers, test_workspace):
    response = await client.post(
        url(test_workspace.id),
        json={"name": "Assistant", "content": LONG},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["token_count"] == 13


async def test_token_count_measures_content_not_name_or_description(
    client, auth_headers, test_workspace
):
    """The count describes the prompt body, so metadata must not leak into it."""
    response = await client.post(
        url(test_workspace.id),
        json={
            "name": "A name that is itself quite long and would score more tokens",
            "description": "A description that is also long enough to skew a count.",
            "content": HELPFUL,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["token_count"] == 6


async def test_empty_content_has_zero_tokens(client, auth_headers, test_workspace):
    response = await client.post(
        url(test_workspace.id),
        json={"name": "Empty", "content": ""},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["token_count"] == 0


async def test_list_prompts_includes_token_count_for_each_prompt(
    client, auth_headers, test_workspace, db_session
):
    db_session.add_all(
        [
            PromptTemplate(workspace_id=test_workspace.id, name="A", content=HELPFUL),
            PromptTemplate(workspace_id=test_workspace.id, name="B", content=TEMPLATED),
        ]
    )
    await db_session.commit()

    response = await client.get(url(test_workspace.id), headers=auth_headers)

    assert response.status_code == 200, response.text
    counts = {p["name"]: p["token_count"] for p in response.json()["prompts"]}
    assert counts == {"A": 6, "B": 16}


async def test_update_prompt_recomputes_token_count(
    client, auth_headers, test_workspace, db_session
):
    """Computed on read, so an edit is reflected without any write to a count column."""
    prompt = PromptTemplate(workspace_id=test_workspace.id, name="Draft", content=HELPFUL)
    db_session.add(prompt)
    await db_session.commit()
    await db_session.refresh(prompt)

    response = await client.put(
        url(test_workspace.id) + f"/{prompt.id}",
        json={"content": LONG},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["token_count"] == 13
