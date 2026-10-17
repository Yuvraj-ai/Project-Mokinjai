"""The built-in tool registry.

A built-in is backend code the platform ships and calls in-process — never in the
sandbox (ADR-010, ADR-015). This module is the authority on which built-ins exist
and on what identifies them.
"""

import inspect
import textwrap
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from app.schemas.tool import ToolSchema
from app.services.tool_schema import extract_schema


@dataclass(frozen=True)
class BuiltinTool:
    """One registered built-in.

    `key` is the identity everything resolves through and never changes. `name` is
    what users read and may change freely. `schema` is derived from the function's
    own source by the same extractor a user-defined tool goes through, so a
    built-in cannot describe itself differently from how it is written.
    """

    key: str
    name: str
    function: Callable[..., Any]
    schema: ToolSchema

    @property
    def description(self) -> str:
        return self.schema.description


BUILTIN_TOOLS: dict[str, BuiltinTool] = {}

_T = TypeVar("_T", bound=Callable[..., Any])


def register_builtin(entry: BuiltinTool) -> BuiltinTool:
    """Add a built-in. Two tools may not claim one key."""
    if entry.key in BUILTIN_TOOLS:
        raise ValueError(f"two built-in tools declare the key '{entry.key}'")
    BUILTIN_TOOLS[entry.key] = entry
    return entry


def tool(key: str, *, name: str | None = None) -> Callable[[_T], _T]:
    """Register a built-in tool.

    The source is checked with the rules a user-defined tool must satisfy, so a
    built-in without a docstring, an `Args:` section, a type hint or a return
    annotation fails at import — loudly — rather than at the moment an agent tries
    to describe it to a model. `inspect.getsource` includes the decorator line and
    keeps the function's own indentation; `textwrap.dedent` is what makes a
    function defined inside another function (as a test's is) parse, and is a no-op
    for a module-level one.
    """
    def decorate(function: _T) -> _T:
        result = extract_schema(textwrap.dedent(inspect.getsource(function)))
        if result.schema is None:
            raise ValueError(
                f"built-in tool '{key}' is not a valid tool: " + " ".join(result.errors)
            )
        register_builtin(
            BuiltinTool(
                key=key,
                name=name or function.__name__,
                function=function,
                schema=result.schema,
            )
        )
        return function

    return decorate


def builtin_tool(key: str) -> BuiltinTool:
    """The built-in registered under `key`. Raises `KeyError` for an unknown key."""
    try:
        return BUILTIN_TOOLS[key]
    except KeyError as exc:
        raise KeyError(f"no built-in tool is registered under '{key}'") from exc


def list_builtin_tools() -> list[BuiltinTool]:
    """Every built-in, ordered by display name."""
    return sorted(BUILTIN_TOOLS.values(), key=lambda entry: entry.name.lower())
