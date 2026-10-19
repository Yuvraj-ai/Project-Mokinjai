"""The LangChain side of an agent run: tools the model can actually call.

No network and no sandbox: the sandbox session is faked, and the search tools are
only constructed (construction does not call a provider).
"""

import json

import pytest

from app.schemas.tool import ToolParameter, ToolSchema
from app.services.agent_tools import (
    knowledge_search_tool,
    read_skill_tool,
    subagent_tool,
    user_tool,
)
from app.services.agent_dependencies import ResolvedSkills
from app.services.sandbox.errors import ErrorInfo, ErrorKind
from app.services.sandbox.session import ToolResult
from app.services.web_search import build_web_search_tool, native_web_search_spec


class FakeSession:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls: list[tuple[str, dict]] = []

    def execute_tool(self, name, args=None, timeout=None):
        self.calls.append((name, args or {}))
        return ToolResult(
            result=self.result,
            stdout="out",
            stderr="err",
            error=self.error,
        )


WEATHER = ToolSchema(
    name="weather",
    description="Look up the weather.",
    parameters=[
        ToolParameter(name="city", type="string", description="City name"),
        ToolParameter(name="days", type="integer", description="Forecast days", required=False),
    ],
)


@pytest.mark.asyncio
async def test_user_tool_exposes_its_schema_and_runs_in_the_session():
    session = FakeSession(result={"temperature": 21})

    tool = user_tool(WEATHER, session)
    assert tool.name == "weather"
    assert tool.description == "Look up the weather."
    assert set(tool.args_schema.model_fields) == {"city", "days"}

    raw = await tool.ainvoke({"city": "Paris"})
    payload = json.loads(raw)
    assert payload["result"] == {"temperature": 21}
    assert payload["stdout"] == "out"
    assert session.calls == [("weather", {"city": "Paris"})]


@pytest.mark.asyncio
async def test_a_sandbox_error_is_returned_as_text_not_raised():
    session = FakeSession(
        error=ErrorInfo(kind=ErrorKind.CODE_ERROR.value, message="division by zero")
    )
    tool = user_tool(WEATHER, session)

    result = await tool.ainvoke({"city": "Paris"})

    assert "division by zero" in result
    assert "error" in result.lower()


@pytest.mark.asyncio
async def test_read_skill_is_case_insensitive_and_names_an_unknown_skill():
    resolved = ResolvedSkills(
        menu=(),
        skill_closure=("SkillA", "SkillB"),
        contents={"SkillA": "Alpha body", "SkillB": "Beta body"},
        tool_names=(),
    )
    tool = read_skill_tool(resolved)

    assert tool.name == "read_skill"
    assert await tool.ainvoke({"name": "skilla"}) == "Alpha body"
    unknown = await tool.ainvoke({"name": "Missing"})
    assert "No skill named" in unknown


@pytest.mark.asyncio
async def test_knowledge_search_is_explicit_about_unavailable_retrieval():
    tool = knowledge_search_tool(["Handbook", "Policies"])

    result = await tool.ainvoke({"query": "holiday allowance"})

    assert "not available" in result.lower()
    assert "Handbook" in result


@pytest.mark.asyncio
async def test_subagent_tool_delegates_to_the_runner():
    seen: list[str] = []

    async def run(task: str) -> str:
        seen.append(task)
        return "child answer"

    tool = subagent_tool(
        agent_id="12345678-abcd", name="Researcher", description="Finds sources", run=run
    )

    assert tool.name.startswith("ask_")
    assert tool.name.replace("_", "").isalnum()
    assert await tool.ainvoke({"task": "find two sources"}) == "child answer"
    assert seen == ["find two sources"]


def test_web_search_tools_are_built_for_the_stored_methods():
    tavily = build_web_search_tool("tavily", "tvly-key")
    exa = build_web_search_tool("exa", "exa-key")

    assert tavily is not None and tavily.name == "tavily_search"
    assert exa is not None and "exa" in exa.name.lower()


def test_native_search_specs_are_provider_specific():
    assert native_web_search_spec("openai") == {"type": "web_search"}
    assert native_web_search_spec("gemini") == {"google_search": {}}
    anthropic = native_web_search_spec("anthropic")
    assert anthropic is not None and anthropic["type"].startswith("web_search")
    assert native_web_search_spec("custom") is None
