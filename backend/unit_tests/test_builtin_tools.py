"""The built-in tool registry.

A built-in is developer-owned backend code that runs without the sandbox
(ADR-015). It is identified by a declared key, and it has to satisfy the same
rules a user-defined tool does — which is why `tool()` runs the extractor over the
function's own source at import.
"""

import inspect

import pytest

from app.schemas.tool import ToolSchema
from app.services.tool_schema import extract_schema
from app.tools import (
    BUILTIN_TOOLS,
    BuiltinTool,
    builtin_tool,
    list_builtin_tools,
    register_builtin,
    tool,
)


@pytest.fixture
def registry():
    """Restore the module-level map afterwards: registration is process-wide."""
    snapshot = dict(BUILTIN_TOOLS)
    yield BUILTIN_TOOLS
    BUILTIN_TOOLS.clear()
    BUILTIN_TOOLS.update(snapshot)


def test_the_registry_ships_builtins():
    assert {"current_time", "word_count"} <= set(BUILTIN_TOOLS)


def test_every_registered_builtin_is_a_valid_tool():
    """The same rules a user-defined tool must satisfy, applied to this repo's code."""
    for key, entry in BUILTIN_TOOLS.items():
        result = extract_schema(inspect.getsource(entry.function))
        assert result.errors == [], f"{key}: {result.errors}"
        assert result.schema is not None


def test_every_builtin_has_a_name_and_a_description():
    for key, entry in BUILTIN_TOOLS.items():
        assert entry.name
        assert entry.description
        assert entry.schema.description == entry.description


def test_lookup_resolves_a_builtin_by_its_key():
    assert builtin_tool("current_time").name == "Current Time"


def test_an_unknown_key_raises():
    with pytest.raises(KeyError):
        builtin_tool("no_such_tool")


def test_builtins_are_listed_by_display_name():
    names = [entry.name for entry in list_builtin_tools()]
    assert names == sorted(names, key=str.lower)


def test_a_key_survives_a_change_of_display_name(registry):
    """The point of the key: renaming what users read moves no identity."""
    schema = ToolSchema(name="handler", description="Do a thing.")

    register_builtin(
        BuiltinTool(key="stable", name="First Name", function=lambda: None, schema=schema)
    )
    assert builtin_tool("stable").name == "First Name"

    registry["stable"] = BuiltinTool(
        key="stable", name="Second Name", function=lambda: None, schema=schema
    )

    assert builtin_tool("stable").name == "Second Name"


def test_a_duplicate_key_is_refused(registry):
    schema = ToolSchema(name="handler", description="Do a thing.")
    register_builtin(
        BuiltinTool(key="dup", name="One", function=lambda: None, schema=schema)
    )

    with pytest.raises(ValueError, match="dup"):
        register_builtin(
            BuiltinTool(key="dup", name="Two", function=lambda: None, schema=schema)
        )


def test_the_decorator_registers_and_returns_the_function(registry):
    @tool(key="decorated", name="Decorated")
    def decorated(value: str) -> str:
        """Describe a value.

        Args:
            value: The value to describe.
        """
        return value

    assert builtin_tool("decorated").schema.name == "decorated"
    assert decorated("x") == "x", "the decorator must not wrap the function"


def test_the_decorator_refuses_source_that_is_not_a_tool(registry):
    with pytest.raises(ValueError, match="no docstring"):

        @tool(key="undocumented")
        def undocumented(value: str) -> str:
            return value


def test_the_display_name_defaults_to_the_function_name(registry):
    @tool(key="defaulted")
    def defaulted(value: str) -> str:
        """Describe a value.

        Args:
            value: The value to describe.
        """
        return value

    assert builtin_tool("defaulted").name == "defaulted"
