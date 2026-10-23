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


# Enough output for a table or a traceback, small enough that a runaway print cannot
# consume the context window. The marker is part of the contract: a silently cut result
# would look complete.
STDOUT_LIMIT = 20_000
TRUNCATION_MARKER = "\n… [truncated]"


def _truncate(text: str) -> str:
    return text if len(text) <= STDOUT_LIMIT else text[:STDOUT_LIMIT] + TRUNCATION_MARKER


def sandbox_python_tool(session: SandboxSession, filenames: list[str]) -> BaseTool:
    """Run Python in the run's sandbox, with the run's files mounted for reading."""

    mounted = ", ".join(filenames) if filenames else "none"

    async def execute_python(code: str) -> str:
        result = await asyncio.to_thread(session.execute_python, code)
        return json.dumps(
            {
                "stdout": _truncate(result.stdout),
                "stderr": _truncate(result.stderr),
                "ok": result.error is None,
                "error": result.error.message if result.error is not None else None,
                "files": [row.name for row in result.generated_files],
            }
        )

    return StructuredTool(
        name="execute_python",
        description=(
            "Run Python to inspect or transform the files attached to this agent. "
            f"Mounted read-only in /app/data: {mounted}. "
            "/app/work is writable scratch; files written to /app/output are captured "
            "and returned by name. pandas, openpyxl, python-docx and pypdf are "
            "installed. There is no network. Print summaries and aggregates, not whole "
            "dataframes or whole files. An exception returns its traceback verbatim. "
            "The default timeout is 30 seconds."
        ),
        args_schema=create_model("SandboxPythonInput", code=(str, Field(description="Python source to run."))),
        coroutine=execute_python,
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
