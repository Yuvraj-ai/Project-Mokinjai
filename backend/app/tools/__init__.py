"""Built-in tools: backend code the platform runs in-process.

Import this package, not its submodules — importing it is what registers the tools
in `app.tools.builtin`, and `app.routers.tools` reads the registry this fills.
"""

from app.tools.builtin import current_time, word_count  # noqa: F401 - registers the built-ins
from app.tools.registry import (
    BUILTIN_TOOLS,
    BuiltinTool,
    builtin_tool,
    list_builtin_tools,
    register_builtin,
    tool,
)

__all__ = [
    "BUILTIN_TOOLS",
    "BuiltinTool",
    "builtin_tool",
    "current_time",
    "list_builtin_tools",
    "register_builtin",
    "tool",
    "word_count",
]
