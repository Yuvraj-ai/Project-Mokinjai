"""The sandbox session: one per agent run (ADR-010).

A run constructs a session and holds it. Nothing starts at construction; the first
call that needs to execute code starts the isolation, and `close()` ends it. An agent
that never executes code therefore never gets a container, which is the "lazy spin-up"
of the recorded design.

Synchronous, with a `threading.Lock`. The work is blocking process and socket I/O, so
keeping it off the event loop is the async runtime's single `to_thread` hop, and it
makes this service directly testable with no event loop — the same reason
`app/services/structured_output.py` is a pure module. The sandbox must not be called on
the event loop.
"""

import atexit
import base64
import json
import os
import shutil
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.logging import logger
from app.services.sandbox.backends import (
    ContainerSpec,
    IsolationBackend,
    SandboxConfig,
    select_backend,
)
from app.services.sandbox.errors import ErrorInfo, ErrorKind, SandboxError
from app.services.sandbox.protocol import JobRequest, KernelResponse, classify
from app.services.sandbox.tools import ToolSource


@dataclass(frozen=True)
class GeneratedFile:
    """A file a job wrote. Contents, not a name and not a storage key.

    The sandbox does not know about object storage (ADR-011 is a separate service), so
    returning contents is what keeps this interface closed. The caller decides whether a
    file is text to index, a blob to store, or a download. The cost is that a call can
    put up to the output tmpfs — 64MB — into the caller's memory.
    """

    name: str
    size: int
    data: bytes


@dataclass(frozen=True)
class ExecResult:
    """The outcome of `execute_python`.

    `stderr` is the code's own error stream; `error` is the sandbox's verdict. A job
    that logs a warning and exits cleanly has a non-empty `stderr` and `error is None`.
    """

    stdout: str
    stderr: str
    error: ErrorInfo | None
    generated_files: list[GeneratedFile] = field(default_factory=list)


@dataclass(frozen=True)
class ToolResult:
    """The outcome of `execute_tool`.

    `memory.md` records this shape as `{result, stdout, stderr, error}`; `generated_files`
    is added, because output is cleared at the start of every job, so a tool's file would
    otherwise be destroyed before any caller could read it.
    """

    result: Any
    stdout: str
    stderr: str
    error: ErrorInfo | None
    generated_files: list[GeneratedFile] = field(default_factory=list)


class SandboxSession:
    """One run's sandbox. Holds no container until code needs one."""

    def __init__(
        self,
        *,
        config: SandboxConfig | None = None,
        data_dir: str | None = None,
        tools: ToolSource | None = None,
        run_id: str | None = None,
    ):
        self._config = config or SandboxConfig.from_settings()
        self._data_dir = Path(data_dir) if data_dir else None
        self._tools = tools
        self._run_id = run_id or uuid.uuid4().hex[:12]
        self._backend: IsolationBackend | None = None
        self._host_root: Path | None = None
        self._spec: ContainerSpec | None = None
        self._started = False
        self._closed = False
        self._lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------------- #

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def started(self) -> bool:
        return self._started and not self._closed

    @property
    def output_dir(self) -> Path | None:
        """The host directory this run's generated files are collected into.

        Exposed for tests and for a caller that wants to watch a long run. The correct
        way to read a run's output is `ExecResult.generated_files`; on the subprocess
        backend this path is also the sandbox's, and inside a container it is not.
        """
        if self._closed:
            return None
        if not self._started:
            self.start()
        if self._spec is None:
            return None
        return Path(self._spec.host_output_dir)

    def start(self) -> None:
        """Create the isolation and boot the kernel. Idempotent.

        Called for you by the first execution, so an agent that never runs code never
        gets a container. Call it directly only to pay the start-up cost up front.
        """
        with self._lock:
            self._start()

    def close(self) -> None:
        """Tear the sandbox down. Idempotent, and safe if it never started.

        The normal path to no zombie containers. It is not the only one: the container's
        own `sleep <max_run_seconds>` bounds its life and `--rm` removes it, and
        `DockerBackend.start` sweeps anything older than that. Between them, a parent
        that dies without calling this leaves nothing running indefinitely.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            atexit.unregister(self.close)
            backend, self._backend = self._backend, None
            try:
                if backend is not None and self._started:
                    try:
                        backend.stop()
                    except Exception as exc:
                        logger.warning(f"Sandbox teardown failed for run {self._run_id}: {exc}")
            finally:
                self._started = False
                if self._host_root is not None:
                    shutil.rmtree(self._host_root, ignore_errors=True)
                    self._host_root = None
                self._spec = None

    def __enter__(self) -> "SandboxSession":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    # -- the start path ----------------------------------------------------- #

    def _start(self) -> None:
        if self._started:
            return
        if self._closed:
            raise SandboxError(
                ErrorKind.CONTAINER_ERROR, "This sandbox session is closed."
            )

        self._host_root = Path(tempfile.mkdtemp(prefix="mokinjay-sandbox-"))
        try:
            ipc_dir = self._host_root / "ipc"
            os.makedirs(ipc_dir, exist_ok=True)
            try:
                os.chmod(ipc_dir, 0o777)
            except OSError:
                pass
            data_dir = self._host_root / "data"
            os.makedirs(data_dir, exist_ok=True)
            # The run's knowledge-base files are staged once and bind-mounted read-only, so
            # a call addresses them by name instead of paying to send them through the
            # socket on every call. The short /tmp root also keeps the Unix socket path
            # under the 107-byte AF_UNIX limit, which a path under the project directory
            # would not.
            if self._data_dir is not None:
                _copy_tree(self._data_dir, data_dir)

            spec: ContainerSpec = self._config.container_spec(run_id=self._run_id, host_root=str(self._host_root))
            self._spec = spec
            backend = select_backend(self._config)(spec)
            self._backend = backend
            backend.start()
        except BaseException:
            if self._host_root is not None:
                shutil.rmtree(self._host_root, ignore_errors=True)
                self._host_root = None
            self._spec = None
            self._backend = None
            raise
        self._started = True
        # A clean interpreter exit closes the sandbox, so an embedder that forgets
        # close() still leaves nothing to the sweep.
        atexit.register(self.close)
        logger.info(f"Sandbox for run {self._run_id} started on the {backend.name} backend")

    def _dispatch(self, request: JobRequest) -> tuple[KernelResponse | None, ErrorInfo | None]:
        """Run one job, with the sandbox's own failures converted into a result's error.

        Never raises for a sandbox failure. The kinds decidable on the host — a missing
        image, an unreachable daemon, a closed session — all have to reach the caller
        the same way a code error does, or the agent loop would need an exception
        handler around every call.
        """
        try:
            self._start()
        except SandboxError as exc:
            return None, exc.info
        if self._backend is None:      # pragma: no cover - guarded by _start
            return None, ErrorInfo(ErrorKind.CONTAINER_ERROR.value, "The sandbox is not available.")
        try:
            response = self._backend.run(
                request, request.timeout + self._config.kernel_grace_seconds
            )
        except SandboxError as exc:
            return None, exc.info
        return response, classify(response)

    def _collect_outputs(self) -> list[GeneratedFile]:
        if self._backend is None:
            return []
        try:
            collected = self._backend.collect_outputs()
        except SandboxError:
            return []
        return [GeneratedFile(name=name, size=len(data), data=data) for name, data in collected]

    # -- execution ---------------------------------------------------------- #

    def execute_python(
        self,
        code: str,
        files: dict[str, bytes] | None = None,
        timeout: float | None = None,
    ) -> ExecResult:
        """Run Python in the run's sandbox and return what it produced.

        `files` are per-call inputs, given as bytes and written into the writable work
        directory before the code runs. Per call because they are small and ad-hoc; the
        run's knowledge-base files are handed to the constructor instead and mounted
        read-only, so they are not sent again on every call.
        """
        request = JobRequest(
            kind="python",
            code=code,
            inputs=_encode_inputs(files) if files else {},
            timeout=float(timeout or self._config.timeout_seconds),
        )
        with self._lock:
            response, error = self._dispatch(request)
            generated = self._collect_outputs()
        return ExecResult(
            stdout=response.stdout if response else "",
            stderr=response.stderr if response else "",
            error=error,
            generated_files=generated,
        )

    def execute_tool(
        self,
        name: str,
        args: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> ToolResult:
        """Run a user-defined tool in the run's sandbox.

        `ctx` is bound as a name in the execution namespace, NOT as a parameter (tools
        spec §7): that keeps "every parameter has a type hint" free of exceptions and
        means the parameters an LLM sees are exactly the ones the user declared. `args`
        fills the function's declared parameters by keyword; a `ctx` key in `args` is
        refused below so it cannot shadow the injected name.

        What `ctx` can reach is in the kernel's `SandboxContext` docstring: it is
        offline, and the capabilities the tool design promised it are host-side tools
        and connectors instead (spec §5).
        """
        if args is not None and not isinstance(args, dict):
            return ToolResult(
                result=None,
                stdout="",
                stderr="",
                error=ErrorInfo(
                    kind=ErrorKind.INVALID_ARGS.value,
                    message=f"'args' must be a mapping, not {type(args).__name__}.",
                ),
            )
        arguments = dict(args or {})
        if "ctx" in arguments:
            return ToolResult(
                result=None,
                stdout="",
                stderr="",
                error=ErrorInfo(
                    kind=ErrorKind.INVALID_ARGS.value,
                    message="'ctx' is injected by the sandbox and cannot be supplied by the caller.",
                ),
            )
        if self._tools is None:
            return ToolResult(
                result=None,
                stdout="",
                stderr="",
                error=ErrorInfo(
                    kind=ErrorKind.TOOL_NOT_FOUND.value,
                    message="No tool source is configured for this session.",
                ),
            )
        source = self._tools.source_for(name)
        if source is None:
            return ToolResult(
                result=None,
                stdout="",
                stderr="",
                error=ErrorInfo(
                    kind=ErrorKind.TOOL_NOT_FOUND.value,
                    message=f"There is no tool named '{name}'.",
                ),
            )

        try:
            json.dumps(arguments)
        except (TypeError, ValueError) as exc:
            return ToolResult(
                result=None,
                stdout="",
                stderr="",
                error=ErrorInfo(
                    kind=ErrorKind.INVALID_ARGS.value,
                    message=f"The arguments for '{name}' cannot be sent to the sandbox: {exc}",
                ),
            )

        request = JobRequest(
            kind="tool",
            tool_name=name,
            tool_source=source,
            tool_args=arguments,
            timeout=float(timeout or self._config.timeout_seconds),
        )
        with self._lock:
            response, error = self._dispatch(request)
            generated = self._collect_outputs()
        return ToolResult(
            result=response.result if response else None,
            stdout=response.stdout if response else "",
            stderr=response.stderr if response else "",
            error=error,
            generated_files=generated,
        )


def _copy_tree(source: Path, target: Path) -> None:
    """Copy `source` into `target`, refusing to follow a link out of the tree."""
    for entry in sorted(source.rglob("*")):
        if entry.is_symlink() or not entry.is_file():
            continue
        destination = target / entry.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, destination)


def _encode_inputs(files: dict[str, bytes]) -> dict[str, str]:
    """Per-call inputs, base64'd for the wire, with names that cannot escape."""
    for name, data in files.items():
        if not name or os.path.isabs(name) or ".." in name.split("/"):
            raise ValueError(f"{name!r} must be a relative path inside the sandbox")
        if not isinstance(data, bytes):
            raise TypeError(f"the contents of {name!r} must be bytes, not {type(data).__name__}")
    return {name: base64.b64encode(data).decode("ascii") for name, data in files.items()}
