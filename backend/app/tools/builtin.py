"""The built-in tools this feature ships.

These are the only tool bodies the backend runs itself; a user-defined tool's body
goes to the sandbox. `@tool` applies the same rules here that the editor applies to
a user — one function, a docstring with an `Args:` section, a type hint on every
parameter, a return annotation — so a file that drifts fails at import.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.tools.registry import tool


@tool(key="current_time", name="Current Time")
def current_time(timezone: str) -> str:
    """Return the current time in a named timezone.

    Args:
        timezone: IANA timezone name, e.g. Europe/London. Falls back to UTC when
            the name is not a known zone.
    """
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    return datetime.now(zone).isoformat()


@tool(key="word_count", name="Word Count")
def word_count(text: str) -> int:
    """Count the words in a piece of text.

    Args:
        text: The text to count. Words are whitespace-separated runs.
    """
    return len(text.split())
