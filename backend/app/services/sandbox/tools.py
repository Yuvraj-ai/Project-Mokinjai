"""Where `execute_tool` gets a user-defined tool's code.

A Protocol, so the sandbox never learns about the `tools` table. The runtime (Phase 3)
supplies the database-backed implementation, this module supplies an in-memory one for
tests and narrow callers, and tool CRUD stays out of the sandbox's scope. That seam is
why "where do tool definitions come from" is not a question this service has to answer.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ToolSource(Protocol):
    """A lookup from a tool's name to the Python source that defines its function."""

    def source_for(self, name: str) -> str | None:
        """The source, or `None` if there is no tool by that name."""


class InMemoryToolSource:
    """A tool source backed by a dict of name to Python source."""

    def __init__(self, sources: dict[str, str]):
        self._sources = dict(sources)

    def source_for(self, name: str) -> str | None:
        return self._sources.get(name)
