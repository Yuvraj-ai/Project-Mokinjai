"""LangChain adapters for the tools an agent exposes to its model.

Every adapter returns a `BaseTool`; nothing here builds a graph or talks to a
provider. The sandbox stays synchronous, so the one blocking call is off-loaded
with `asyncio.to_thread` — the runtime's single hop, as the sandbox documents.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Awaitable, Callable

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from app.schemas.tool import ParameterType, ToolSchema
from app.services.agent_dependencies import ResolvedSkills
from app.services.sandbox.session import SandboxSession

_PYTHON_TYPE: dict[str, Any] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
    "any": Any,
}


class SubagentInput(BaseModel):
    task: str = Field(
        description="What the subagent should do, including any context it needs."
    )


def user_tool(schema: ToolSchema, session: SandboxSession) -> BaseTool:
    """A user-defined tool, executed in the run's sandbox by name."""

    async def call(**kwargs: Any) -> str:
        # An optional parameter the model left out must not become None: the
        # user's function may not accept an explicit None for it.
        supplied = {key: value for key, value in kwargs.items() if value is not None}
        result = await asyncio.to_thread(session.execute_tool, schema.name, supplied)
        if result.error is not None:
            return f"Tool error ({result.error.kind}): {result.error.message}"
        return json.dumps(
            {"result": result.result, "stdout": result.stdout, "stderr": result.stderr},
            default=str,
        )

    return StructuredTool(
        name=schema.name,
        description=schema.description,
        args_schema=_args_model(schema),
        coroutine=call,
    )


def read_skill_tool(resolved: ResolvedSkills) -> BaseTool:
    contents = {name.lower(): body for name, body in resolved.contents.items()}

    def read_skill(name: str) -> str:
        """Return the full instructions for one of the agent's skills."""
        return contents.get(name.strip().lower(), f"No skill named '{name}'.")

    return StructuredTool.from_function(
        func=read_skill,
        name="read_skill",
        description=(
            "Return the full instructions for one of the agent's skills. "
            "The skill menu lists the names."
        ),
    )


def knowledge_search_tool(knowledge_base_names: list[str]) -> BaseTool:
    selected = ", ".join(knowledge_base_names) if knowledge_base_names else "none selected"

    def knowledge_search(query: str) -> str:
        """Search the agent's knowledge bases for passages relevant to a query."""
        return (
            f"Knowledge base retrieval is not available yet, so '{query}' could not be "
            f"searched. Selected knowledge bases: {selected}. Answer from what you already "
            "know and say that you could not check the knowledge base."
        )

    return StructuredTool.from_function(
        func=knowledge_search,
        name="knowledge_search",
        description="Search the agent's knowledge bases for relevant passages.",
    )


def subagent_tool(
    *,
    agent_id: str,
    name: str,
    description: str | None,
    run: Callable[[str], Awaitable[str]],
) -> BaseTool:
    async def call(task: str) -> str:
        return await run(task)

    return StructuredTool.from_function(
        coroutine=call,
        name=_subagent_tool_name(name, agent_id),
        description=description or f"Delegate a task to the {name} agent.",
        args_schema=SubagentInput,
    )


def _args_model(schema: ToolSchema) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for parameter in schema.parameters:
        annotation = _annotation(parameter.type, parameter.items_type)
        if parameter.required:
            fields[parameter.name] = (annotation, Field(description=parameter.description))
        else:
            fields[parameter.name] = (
                annotation | None,
                Field(default=None, description=parameter.description),
            )
    return create_model(f"{schema.name}_input", **fields)


def _annotation(kind: ParameterType, items_type: str | None) -> Any:
    if kind == "array":
        return list[_PYTHON_TYPE.get(items_type or "any", Any)]
    return _PYTHON_TYPE.get(kind, Any)


def _subagent_tool_name(name: str, agent_id: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:40] or "agent"
    return f"ask_{slug}_{agent_id[:4]}"
