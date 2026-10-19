"""Agent API: persistence, validation, resolution and ordering.

Capability lookup is patched to a fixed model profile so no test touches
models.dev; the lookup itself is covered in `test_agent_capabilities.py`.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.agent import Agent, AgentSkill, AgentSubagent, AgentTool
from app.models.connector import ConnectorInstance
from app.models.execution import Execution
from app.models.knowledge import KnowledgeBase
from app.models.llm_profile import LlmProfile
from app.models.resource_usage import bump_usage
from app.models.search_credential import SearchCredential
from app.models.skill import Skill
from app.models.structured_output import StructuredOutput
from app.models.tool import Tool


@pytest.fixture(autouse=True)
def fixed_model_profile(monkeypatch):
    monkeypatch.setattr(
        "app.services.agent_capabilities.lookup_profile",
        lambda provider, model_id: {
            "max_output_tokens": 4096,
            "reasoning_effort_levels": ["low", "medium", "high"],
        },
    )


def url(workspace_id: str) -> str:
    return f"/api/workspaces/{workspace_id}/agents"


async def make_profile(db_session, workspace_id, *, name="Primary", status="verified"):
    profile = LlmProfile(
        workspace_id=workspace_id,
        name=name,
        provider="openai",
        model_id="gpt-4o-mini",
        encrypted_api_key=b"ciphertext",
        context_window=128000,
        compaction_at_tokens=102400,
        input_price_per_million=0.15,
        output_price_per_million=0.6,
        cache_price_per_million=0.0,
        status=status,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


def payload(profile_id: str, **overrides):
    body = {
        "name": "Support Agent",
        "description": "Answers questions",
        "llm_profile_id": profile_id,
        "system_prompt": "You are helpful.",
        "params": {"temperature": 0.4, "max_tokens": 2048, "streaming": True},
        "skill_ids": [],
        "tool_ids": [],
        "knowledge_base_ids": [],
        "connector_ids": [],
        "subagent_ids": [],
    }
    body.update(overrides)
    return body


@pytest_asyncio.fixture
async def profile(db_session, test_workspace):
    return await make_profile(db_session, test_workspace.id)


@pytest.mark.asyncio
async def test_round_trip(client, test_workspace, auth_headers, profile):
    base = url(test_workspace.id)

    created = await client.post(base, json=payload(profile.id), headers=auth_headers)
    assert created.status_code == 201, created.text
    body = created.json()
    agent_id = body["id"]
    assert body["name"] == "Support Agent"
    assert body["params"]["max_tokens"] == 2048
    assert body["status"] == "ready"
    assert body["issues"] == []
    assert body["capabilities"]["max_output_tokens"] == 4096

    listed = await client.get(base, headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["agents"][0]["id"] == agent_id

    fetched = await client.get(f"{base}/{agent_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["system_prompt"] == "You are helpful."

    updated = await client.put(
        f"{base}/{agent_id}",
        json=payload(profile.id, name="Renamed", params={"max_tokens": 100}),
        headers=auth_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["params"] == {"max_tokens": 100}

    deleted = await client.delete(f"{base}/{agent_id}", headers=auth_headers)
    assert deleted.status_code == 200
    assert deleted.json() == {"success": True}
    assert (await client.get(base, headers=auth_headers)).json()["total"] == 0


@pytest.mark.asyncio
async def test_name_is_unique_case_insensitively(client, test_workspace, auth_headers, profile):
    base = url(test_workspace.id)
    first = await client.post(base, json=payload(profile.id, name="Support"), headers=auth_headers)
    assert first.status_code == 201

    second = await client.post(base, json=payload(profile.id, name="support"), headers=auth_headers)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_the_profile_must_exist_and_be_verified(
    client, test_workspace, auth_headers, db_session
):
    base = url(test_workspace.id)

    missing = await client.post(base, json=payload("does-not-exist"), headers=auth_headers)
    assert missing.status_code == 422
    assert missing.json()["detail"][0]["loc"][-1] == "llm_profile_id"

    failed = await make_profile(db_session, test_workspace.id, name="Failed", status="failed")
    rejected = await client.post(base, json=payload(failed.id), headers=auth_headers)
    assert rejected.status_code == 422
    assert "verified" in rejected.json()["detail"][0]["msg"]


@pytest.mark.asyncio
async def test_params_are_range_checked(client, test_workspace, auth_headers, profile):
    base = url(test_workspace.id)
    response = await client.post(
        base,
        json=payload(profile.id, params={"max_tokens": 4097, "temperature": 9}),
        headers=auth_headers,
    )
    assert response.status_code == 422
    fields = {error["loc"][-1] for error in response.json()["detail"]}
    assert fields == {"params.max_tokens", "params.temperature"}


@pytest.mark.asyncio
async def test_skills_resolve_to_a_closure_and_lock_their_tools(
    client, test_workspace, auth_headers, profile, db_session
):
    skill_a = Skill(
        workspace_id=test_workspace.id,
        name="SkillA",
        description="Top",
        content="Use /tool_a and @SkillB.",
    )
    skill_b = Skill(
        workspace_id=test_workspace.id,
        name="SkillB",
        description="Nested",
        content="Use /tool_b.",
    )
    tool_a = Tool(
        workspace_id=test_workspace.id,
        name="tool_a",
        code="def tool_a():\n    return 1",
    )
    tool_b = Tool(
        workspace_id=test_workspace.id,
        name="tool_b",
        code="def tool_b():\n    return 2",
    )
    direct = Tool(
        workspace_id=test_workspace.id,
        name="tool_direct",
        code="def tool_direct():\n    return 3",
    )
    db_session.add_all([skill_a, skill_b, tool_a, tool_b, direct])
    await db_session.commit()

    created = await client.post(
        url(test_workspace.id),
        json=payload(
            profile.id,
            skill_ids=[skill_a.id],
            tool_ids=[direct.id],
        ),
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()

    assert body["skill_ids"] == [skill_a.id]
    assert body["tool_ids"] == [direct.id]
    resolved_skills = body["resolved"]["skills"]
    assert {(item["name"], item["root"]) for item in resolved_skills} == {
        ("SkillA", True),
        ("SkillB", False),
    }
    resolved_tools = {item["name"]: item for item in body["resolved"]["tools"]}
    assert resolved_tools["tool_a"]["locked"] is True
    assert resolved_tools["tool_b"]["locked"] is True
    assert resolved_tools["tool_direct"]["locked"] is False
    assert resolved_tools["tool_a"]["source"] == "workspace"

    rows = (
        await db_session.execute(
            select(AgentSkill.skill_id).where(AgentSkill.agent_id == body["id"])
        )
    ).scalars().all()
    assert rows == [skill_a.id]


@pytest.mark.asyncio
async def test_update_replaces_the_composition(
    client, test_workspace, auth_headers, profile, db_session
):
    skill = Skill(
        workspace_id=test_workspace.id, name="Keeper", description="D", content="Do it."
    )
    tool = Tool(
        workspace_id=test_workspace.id, name="kept_tool", code="def kept_tool():\n    return 1"
    )
    db_session.add_all([skill, tool])
    await db_session.commit()

    created = await client.post(
        url(test_workspace.id),
        json=payload(profile.id, skill_ids=[skill.id], tool_ids=[tool.id]),
        headers=auth_headers,
    )
    agent_id = created.json()["id"]

    updated = await client.put(
        f"{url(test_workspace.id)}/{agent_id}",
        json=payload(profile.id),
        headers=auth_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["skill_ids"] == []
    assert updated.json()["tool_ids"] == []

    remaining = await db_session.execute(select(AgentTool).where(AgentTool.agent_id == agent_id))
    assert remaining.scalars().all() == []


@pytest.mark.asyncio
async def test_a_referenced_subagent_blocks_deletion(
    client, test_workspace, auth_headers, profile, db_session
):
    base = url(test_workspace.id)
    child = await client.post(
        base, json=payload(profile.id, name="Child"), headers=auth_headers
    )
    parent = await client.post(
        base,
        json=payload(profile.id, name="Parent", subagent_ids=[child.json()["id"]]),
        headers=auth_headers,
    )
    assert parent.status_code == 201, parent.text

    blocked = await client.delete(f"{base}/{child.json()['id']}", headers=auth_headers)
    assert blocked.status_code == 409
    assert "Parent" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_subagent_self_selection_and_cycles_are_refused(
    client, test_workspace, auth_headers, profile, db_session
):
    base = url(test_workspace.id)
    first = await client.post(base, json=payload(profile.id, name="First"), headers=auth_headers)
    second = await client.post(base, json=payload(profile.id, name="Second"), headers=auth_headers)

    self_link = await client.put(
        f"{base}/{first.json()['id']}",
        json=payload(profile.id, name="First", subagent_ids=[first.json()["id"]]),
        headers=auth_headers,
    )
    assert self_link.status_code == 422

    linked = await client.put(
        f"{base}/{first.json()['id']}",
        json=payload(profile.id, name="First", subagent_ids=[second.json()["id"]]),
        headers=auth_headers,
    )
    assert linked.status_code == 200, linked.text

    cycle = await client.put(
        f"{base}/{second.json()['id']}",
        json=payload(profile.id, name="Second", subagent_ids=[first.json()["id"]]),
        headers=auth_headers,
    )
    assert cycle.status_code == 422
    assert "cycle" in cycle.json()["detail"][0]["msg"].lower()


@pytest.mark.asyncio
async def test_options_put_the_least_recently_used_first(
    client, test_workspace, auth_headers, db_session
):
    from datetime import datetime, timedelta, timezone

    older = await make_profile(db_session, test_workspace.id, name="Older")
    newer = await make_profile(db_session, test_workspace.id, name="Newer")
    older.created_at = datetime.now(timezone.utc) - timedelta(days=10)
    await db_session.commit()

    # Using the older profile should raise it above the newer one.
    await bump_usage(db_session, test_workspace.id, "llm_profile", older.id)
    await db_session.commit()

    response = await client.get(f"{url(test_workspace.id)}/options", headers=auth_headers)
    assert response.status_code == 200
    names = [item["name"] for item in response.json()["llm_profiles"]]
    assert names.index("Older") < names.index("Newer")
    assert response.json()["llm_profiles"][0]["capabilities"]["max_output_tokens"] == 4096


@pytest.mark.asyncio
async def test_options_exclude_the_agent_being_edited(
    client, test_workspace, auth_headers, profile
):
    created = await client.post(
        url(test_workspace.id), json=payload(profile.id), headers=auth_headers
    )
    response = await client.get(
        f"{url(test_workspace.id)}/options?agent_id={created.json()['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["agents"] == []


@pytest.mark.asyncio
async def test_web_search_requires_a_stored_key(
    client, test_workspace, auth_headers, profile, db_session
):
    base = url(test_workspace.id)
    without = await client.post(
        base,
        json=payload(profile.id, web_search={"enabled": True, "method": "tavily"}),
        headers=auth_headers,
    )
    assert without.status_code == 422
    assert without.json()["detail"][0]["loc"][-1] == "web_search"

    db_session.add(
        SearchCredential(
            workspace_id=test_workspace.id, provider="tavily", encrypted_api_key=b"key"
        )
    )
    await db_session.commit()

    with_key = await client.post(
        base,
        json=payload(profile.id, web_search={"enabled": True, "method": "tavily"}),
        headers=auth_headers,
    )
    assert with_key.status_code == 201, with_key.text
    assert with_key.json()["web_search"] == {"enabled": True, "method": "tavily"}


@pytest.mark.asyncio
async def test_references_must_exist(client, test_workspace, auth_headers, profile):
    response = await client.post(
        url(test_workspace.id),
        json=payload(
            profile.id,
            structured_output_id="missing-output",
            knowledge_base_ids=["missing-kb"],
        ),
        headers=auth_headers,
    )
    assert response.status_code == 422
    fields = {error["loc"][-1] for error in response.json()["detail"]}
    assert fields == {"structured_output_id", "knowledge_base_ids"}


@pytest.mark.asyncio
async def test_a_connector_must_be_enabled(
    client, test_workspace, auth_headers, profile, db_session
):
    connector = ConnectorInstance(
        workspace_id=test_workspace.id,
        connector_type="github",
        name="GitHub",
        status="error",
        config={},
        tool_names=[],
    )
    db_session.add(connector)
    await db_session.commit()

    response = await client.post(
        url(test_workspace.id),
        json=payload(profile.id, connector_ids=[connector.id]),
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "connector_ids"


@pytest.mark.asyncio
async def test_a_structured_output_must_compile(
    client, test_workspace, auth_headers, profile, db_session
):
    output = StructuredOutput(
        workspace_id=test_workspace.id,
        name="Answer",
        description="An answer",
        fields=[{"name": "text", "type": "string", "description": "The answer"}],
    )
    db_session.add(output)
    await db_session.commit()

    response = await client.post(
        url(test_workspace.id),
        json=payload(profile.id, structured_output_id=output.id),
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["structured_output_id"] == output.id


@pytest.mark.asyncio
async def test_list_flags_a_profile_that_is_no_longer_verified(
    client, test_workspace, auth_headers, profile, db_session
):
    created = await client.post(
        url(test_workspace.id), json=payload(profile.id), headers=auth_headers
    )
    assert created.json()["status"] == "ready"

    profile.status = "failed"
    await db_session.commit()

    listed = await client.get(url(test_workspace.id), headers=auth_headers)
    item = listed.json()["agents"][0]
    assert item["status"] == "needs_attention"

    fetched = await client.get(
        f"{url(test_workspace.id)}/{created.json()['id']}", headers=auth_headers
    )
    assert fetched.json()["issues"]


@pytest.mark.asyncio
async def test_viewers_can_read_but_not_write(
    client, test_workspace, viewer_headers, profile
):
    base = url(test_workspace.id)
    assert (await client.get(base, headers=viewer_headers)).status_code == 200
    denied = await client.post(base, json=payload(profile.id), headers=viewer_headers)
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_a_prompt_can_be_the_recorded_source(
    client, test_workspace, auth_headers, profile, db_session
):
    from app.models.prompt import PromptTemplate

    prompt = PromptTemplate(
        workspace_id=test_workspace.id,
        name="Source",
        description="Original",
        content="Original text",
    )
    db_session.add(prompt)
    await db_session.commit()

    created = await client.post(
        url(test_workspace.id),
        json=payload(profile.id, system_prompt="Edited text", source_prompt_id=prompt.id),
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["source_prompt_id"] == prompt.id
    assert body["system_prompt"] == "Edited text"

    prompt.content = "Changed later"
    await db_session.commit()
    fetched = await client.get(f"{url(test_workspace.id)}/{body['id']}", headers=auth_headers)
    assert fetched.json()["system_prompt"] == "Edited text"


@pytest.mark.asyncio
async def test_chat_streams_sse_and_records_a_chat_execution(
    client, test_workspace, auth_headers, profile, db_session, monkeypatch
):
    created = await client.post(
        url(test_workspace.id), json=payload(profile.id), headers=auth_headers
    )
    agent_id = created.json()["id"]

    async def fake_stream(workspace_id, streamed_agent_id, messages, execution_id):
        yield {"event": "token", "data": {"delta": "Hi"}}
        yield {
            "event": "done",
            "data": {"execution_id": execution_id, "usage": {}, "cost_usd": 0.0},
        }

    monkeypatch.setattr("app.routers.agents.stream_chat", fake_stream)

    response = await client.post(
        f"{url(test_workspace.id)}/{agent_id}/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: token" in response.text
    assert '"delta": "Hi"' in response.text
    assert "event: done" in response.text

    executions = (
        await db_session.execute(select(Execution).where(Execution.agent_id == agent_id))
    ).scalars().all()
    assert len(executions) == 1
    assert executions[0].trigger_type == "chat"
    assert executions[0].input_data["messages"][0]["content"] == "hello"


@pytest.mark.asyncio
async def test_chat_rejects_an_empty_conversation(
    client, test_workspace, auth_headers, profile
):
    created = await client.post(
        url(test_workspace.id), json=payload(profile.id), headers=auth_headers
    )
    response = await client.post(
        f"{url(test_workspace.id)}/{created.json()['id']}/chat",
        json={"messages": []},
        headers=auth_headers,
    )
    assert response.status_code == 422
