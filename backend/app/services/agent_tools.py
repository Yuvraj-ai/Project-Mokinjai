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

from app.crypto import decrypt_api_key
from app.models.external_database import ExternalDatabaseConnection
from app.schemas.tool import ParameterType, ToolSchema
from app.services.agent_dependencies import ResolvedSkills
from app.services.data_sources.postgres import DataSourceError, describe, run
from app.services.data_sources.guard import GuardError
from app.services.data_sources.ssrf import BlockedHostError, assert_dial_allowed
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


# ---------------------------------------------------------------------------
# External data sources (D2, D4, D6): host-side, in-process tools. The Docker
# sandbox never sees a URI — these run where the credentials already live.

QUERY_DATA_SOURCE = "query_data_source"
DESCRIBE_DATA_SOURCE = "describe_data_source"


class _QueryDataSourceInput(BaseModel):
    connection_id: str = Field(description="The connection_id of the data source to query.")
    sql: str = Field(
        description="A single read-only SELECT statement. Only the tables listed for this "
        "data source may appear in the query."
    )


class _DescribeDataSourceInput(BaseModel):
    connection_id: str = Field(description="The connection_id of the data source to describe.")


def query_data_source_tool(
    connection: "ExternalDatabaseConnection", tables: list[str], agent_id: str | None = None
) -> BaseTool:
    """One read-only SELECT against one attached connection, validated and bounded."""

    async def call(connection_id: str, sql: str) -> str:
        if connection_id != connection.id:
            return f"Unknown data source: {connection_id}"
        uri = decrypt_api_key(connection.encrypted_uri)
        try:
            assert_dial_allowed(uri)
        except BlockedHostError as exc:
            return f"Connection refused: {exc}"
        try:
            result = await run(
                uri, sql, tables, agent_id=agent_id, connection_id=connection.id
            )
        except GuardError as exc:
            return f"Query refused: {exc.reason}"
        except DataSourceError as exc:
            return f"Query failed: {exc}"
        return json.dumps(
            {
                "columns": result.columns,
                "rows": result.rows,
                "row_count": result.row_count,
                "truncated": result.truncated,
            },
            default=str,
        )

    return StructuredTool(
        name=QUERY_DATA_SOURCE,
        description=(
            f"Run one read-only SELECT against the '{connection.name}' data source. "
            f"Allowed tables: {', '.join(tables)}."
        ),
        args_schema=_QueryDataSourceInput,
        coroutine=call,
    )


def describe_data_source_tool(
    connection: "ExternalDatabaseConnection", tables: list[str]
) -> BaseTool:
    """The live table/column list for one attached connection."""

    async def call(connection_id: str) -> str:
        if connection_id != connection.id:
            return f"Unknown data source: {connection_id}"
        uri = decrypt_api_key(connection.encrypted_uri)
        try:
            assert_dial_allowed(uri)
        except BlockedHostError as exc:
            return f"Connection refused: {exc}"
        try:
            schema = await describe(uri)
        except DataSourceError as exc:
            return f"Describe failed: {exc}"
        return json.dumps(
            {
                "tables": [
                    {
                        "schema": table.schema,
                        "name": table.name,
                        "columns": [
                            {"name": c.name, "type": c.type, "nullable": c.nullable}
                            for c in table.columns
                        ],
                    }
                    for table in schema
                ]
            },
            default=str,
        )

    return StructuredTool(
        name=DESCRIBE_DATA_SOURCE,
        description=(
            f"List the tables and columns of the '{connection.name}' data source. "
            f"Only these tables are queryable: {', '.join(tables)}."
        ),
        args_schema=_DescribeDataSourceInput,
        coroutine=call,
    )
