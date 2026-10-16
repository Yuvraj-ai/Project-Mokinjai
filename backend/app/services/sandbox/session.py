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
import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path

from app.logging import logger
from app.services.sandbox.backends import (
    IsolationBackend,
    SandboxConfig,
    select_backend,
)
from app.services.sandbox.errors import ErrorKind, SandboxError


class SandboxSession:
    """One run's sandbox. Holds no container until code needs one."""

    def __init__(
        self,
        *,
        config: SandboxConfig | None = None,
        data_dir: str | None = None,
        run_id: str | None = None,
    ):
        self._config = config or SandboxConfig.from_settings()
        self._data_dir = Path(data_dir) if data_dir else None
        self._run_id = run_id or uuid.uuid4().hex[:12]
        self._backend: IsolationBackend | None = None
        self._host_root: Path | None = None
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
            if backend is not None and self._started:
                try:
                    backend.stop()
                except SandboxError as exc:
                    logger.warning(f"Sandbox teardown failed for run {self._run_id}: {exc}")
            self._started = False
            if self._host_root is not None:
                shutil.rmtree(self._host_root, ignore_errors=True)
                self._host_root = None

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
        os.makedirs(self._host_root / "ipc", exist_ok=True)
        data_dir = self._host_root / "data"
        os.makedirs(data_dir, exist_ok=True)
        # The run's knowledge-base files are staged once and bind-mounted read-only, so
        # a call addresses them by name instead of paying to send them through the
        # socket on every call. The short /tmp root also keeps the Unix socket path
        # under the 107-byte AF_UNIX limit, which a path under the project directory
        # would not.
        if self._data_dir is not None:
            _copy_tree(self._data_dir, data_dir)

        spec = self._config.container_spec(run_id=self._run_id, host_root=str(self._host_root))
        backend = select_backend(self._config)(spec)
        self._backend = backend
        try:
            backend.start()
        except SandboxError:
            shutil.rmtree(self._host_root, ignore_errors=True)
            self._host_root = None
            raise
        self._started = True
        # A clean interpreter exit closes the sandbox, so an embedder that forgets
        # close() still leaves nothing to the sweep.
        atexit.register(self.close)
        logger.info(f"Sandbox for run {self._run_id} started on the {backend.name} backend")


def _copy_tree(source: Path, target: Path) -> None:
    """Copy `source` into `target`, refusing to follow a link out of the tree."""
    for entry in sorted(source.rglob("*")):
        if entry.is_symlink() or not entry.is_file():
            continue
        destination = target / entry.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(entry, destination)
