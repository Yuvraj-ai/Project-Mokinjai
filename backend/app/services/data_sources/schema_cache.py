"""Per-connection schema cache (D6): 60 s TTL, in-process, not persisted.

A PATCH to the connection invalidates the entry, so renamed or re-pointed
connections never serve stale schemas; schema changes on the database side
propagate within a minute.
"""

import time

TTL_SECONDS = 60

# {connection_id: (monotonic_stamp, payload)} — module-level by design: one
# process, in-process cache only (spec: not persisted).
_CACHE: dict[str, tuple[float, dict]] = {}


def get(connection_id: str) -> dict | None:
    entry = _CACHE.get(connection_id)
    if entry is None:
        return None
    stamp, payload = entry
    if time.monotonic() - stamp > TTL_SECONDS:
        _CACHE.pop(connection_id, None)
        return None
    return payload


def set(connection_id: str, payload: dict) -> None:
    _CACHE[connection_id] = (time.monotonic(), payload)


def invalidate(connection_id: str) -> None:
    _CACHE.pop(connection_id, None)
