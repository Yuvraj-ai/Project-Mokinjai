"""How much sandbox memory this process has handed out, per workspace.

The tier in `backends.py` sizes one container. This module bounds the sum, so a
workspace cannot start runs until the host is out of memory: forty 95 MiB runs would
otherwise each ask for 2 GB.

shortcut: the budget is per process, so two workers can each admit 4 GB; move it to
Redis when the backend runs with more than one worker.
"""

import threading

# One workspace's in-flight sandboxes. Chosen so a single 2 GB run plus two 1 GB runs
# still fits on a small host while a burst of large runs is refused rather than OOM.
WORKSPACE_LIMIT_MB = 4096

_lock = threading.Lock()
_used: dict[str, int] = {}


def reserve(workspace_id: str, mb: int) -> bool:
    """Admit `mb` more megabytes for this workspace, or refuse without changing state."""
    with _lock:
        used = _used.get(workspace_id, 0)
        if used + mb > WORKSPACE_LIMIT_MB:
            return False
        _used[workspace_id] = used + mb
        return True


def release(workspace_id: str, mb: int) -> None:
    """Give `mb` back. Releasing more than was reserved cannot drive the count negative."""
    with _lock:
        remaining = _used.get(workspace_id, 0) - mb
        if remaining > 0:
            _used[workspace_id] = remaining
        else:
            _used.pop(workspace_id, None)


def used_mb(workspace_id: str) -> int:
    """The workspace's current reservation, for tests and diagnostics."""
    with _lock:
        return _used.get(workspace_id, 0)


def reset() -> None:
    """Drop every reservation. Test-only: a leaked reservation would otherwise outlive
    the test that made it."""
    with _lock:
        _used.clear()
