"""The sandbox error taxonomy.

`stderr` and `error` answer different questions. `stderr` is the executed code's own
error stream: a job that logs a warning and exits cleanly has a non-empty `stderr`
and no `error`. `error` is the sandbox's verdict, and it is `None` when the code ran
and returned. Every distinct failure the sandbox can observe gets its own kind,
because an exception inside the code, a timeout, an out-of-memory kill and a container
that never started must not look alike to the caller.
"""

from dataclasses import dataclass
from enum import Enum


class ErrorKind(str, Enum):
    """What went wrong. The value is the string that crosses the wire."""

    CODE_ERROR = "code_error"                # the executed code raised
    TIMEOUT = "timeout"                      # the job's deadline was reached
    RESOURCE_LIMIT = "resource_limit"        # the container was killed by a limit
    CONTAINER_ERROR = "container_error"      # the isolation itself failed
    IMAGE_MISSING = "image_missing"          # the sandbox image is not built
    BACKEND_UNAVAILABLE = "backend_unavailable"  # no isolation backend could be chosen
    TOOL_NOT_FOUND = "tool_not_found"        # execute_tool for a name that does not exist
    INVALID_ARGS = "invalid_args"            # arguments that cannot cross the wire


@dataclass(frozen=True)
class ErrorInfo:
    """A classified failure. Plain data, so it crosses the run boundary as JSON."""

    kind: str
    message: str
    detail: str | None = None


class SandboxError(Exception):
    """The sandbox could not run the code at all.

    Distinct from an `error` inside a result, which means the code *ran* and failed.
    Raised from selection and construction — where there is no result to put an error
    in — and converted into a result's `error` by the session.
    """

    def __init__(self, kind: str, message: str, detail: str | None = None):
        super().__init__(message)
        self.info = ErrorInfo(kind=kind, message=message, detail=detail)
