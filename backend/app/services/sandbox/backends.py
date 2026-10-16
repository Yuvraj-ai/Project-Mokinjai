"""Where the kernel runs, and what it can touch.

`IsolationBackend` is the seam ADR-010 needs: the session above it is identical
whether the kernel is inside a container or a plain process, so the Docker backend is
one implementation of an interface rather than the interface itself.

A `Protocol` rather than an ABC, deliberately. The tests need to stand in a fake
backend — to assert lazy start, ordering and teardown without a container — and
structural typing lets a small object do that without inheriting anything. The two
real backends also share no code worth inheriting: one builds a `docker run` command,
the other a `Popen`.
"""

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, ClassVar, Protocol, runtime_checkable

from app.config import get_settings
from app.logging import logger
from app.services.sandbox.errors import ErrorKind, SandboxError
from app.services.sandbox.protocol import JobRequest, KernelResponse, send_request

# The kernel is one file, and the subprocess backend runs exactly the file that the
# image bakes in, so there is a single source of truth for what executes code.
KERNEL_PATH = Path(__file__).with_name("kernel.py")


@dataclass(frozen=True)
class ContainerSpec:
    """The isolation contract: everything both backends are asked to honour.

    The Docker backend turns these into `run` flags. The subprocess backend honours
    what a plain process can — a time limit, a throwaway working directory — and
    cannot honour what it cannot: there is no network namespace to remove and no
    read-only root to impose. That asymmetry is stated at the top of the fallback's
    docstring rather than hidden.
    """

    name: str
    image: str
    memory: str
    cpus: str
    user: str
    network: str
    read_only: bool
    host_root: str
    output_tmpfs_mb: int
    work_tmpfs_mb: int
    max_run_seconds: int
    socket_name: str = "kernel.sock"
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def host_ipc_dir(self) -> str:
        return os.path.join(self.host_root, "ipc")

    @property
    def host_data_dir(self) -> str:
        return os.path.join(self.host_root, "data")

    @property
    def host_work_dir(self) -> str:
        return os.path.join(self.host_root, "work")

    @property
    def host_output_dir(self) -> str:
        return os.path.join(self.host_root, "output")

    @property
    def host_socket_path(self) -> str:
        return os.path.join(self.host_ipc_dir, self.socket_name)


@dataclass(frozen=True)
class SandboxConfig:
    """The sandbox's limits, resolved once from `Settings`.

    A dataclass rather than raw settings so a test can state a limit — a half-second
    timeout, say — without mutating the process-wide settings object.
    """

    backend: str = "auto"
    image: str = "mokinjay-sandbox:1"
    docker_bin: str = "docker"
    memory: str = "256m"
    cpus: str = "0.5"
    user: str = "1000:1000"
    network: str = "none"
    read_only: bool = True
    output_tmpfs_mb: int = 64
    work_tmpfs_mb: int = 64
    timeout_seconds: float = 30.0
    kernel_grace_seconds: float = 10.0
    max_run_seconds: int = 1800

    @classmethod
    def from_settings(cls, settings=None) -> "SandboxConfig":
        settings = settings or get_settings()
        return cls(
            backend=settings.SANDBOX_BACKEND,
            image=settings.SANDBOX_IMAGE,
            docker_bin=settings.SANDBOX_DOCKER_BIN,
            memory=settings.SANDBOX_MEMORY,
            cpus=settings.SANDBOX_CPUS,
            output_tmpfs_mb=settings.SANDBOX_OUTPUT_TMPFS_MB,
            work_tmpfs_mb=settings.SANDBOX_WORK_TMPFS_MB,
            timeout_seconds=settings.SANDBOX_TIMEOUT_SECONDS,
            kernel_grace_seconds=settings.SANDBOX_KERNEL_GRACE_SECONDS,
            max_run_seconds=settings.SANDBOX_MAX_RUN_SECONDS,
        )

    def container_spec(self, *, run_id: str, host_root: str) -> ContainerSpec:
        return ContainerSpec(
            name=f"mokinjay-sandbox-{run_id}",
            image=self.image,
            memory=self.memory,
            cpus=self.cpus,
            user=self.user,
            network=self.network,
            read_only=self.read_only,
            host_root=host_root,
            output_tmpfs_mb=self.output_tmpfs_mb,
            work_tmpfs_mb=self.work_tmpfs_mb,
            max_run_seconds=self.max_run_seconds,
            labels={"mokinjay.run": run_id},
        )


@runtime_checkable
class IsolationBackend(Protocol):
    """One way of isolating the kernel. Two exist: Docker and a plain subprocess."""

    name: ClassVar[str]

    def start(self) -> None:
        """Create the isolation and boot the kernel. Idempotent per instance."""

    def stop(self) -> None:
        """Tear the isolation down. Idempotent, and safe if `start` never ran."""

    def is_alive(self) -> bool:
        """Whether the kernel is still there to answer a job."""

    def run(self, request: JobRequest, timeout: float) -> KernelResponse:
        """Send one job and read its reply.

        `timeout` is the *host's* patience, which must exceed the job's own limit; it
        is the backstop for a job that defers signals. Raises `SandboxError` when the
        sandbox fails, which is not the same as the code failing.
        """

    def collect_outputs(self) -> list[tuple[str, bytes]]:
        """This job's generated files, as `(relative path, contents)` pairs."""


def kernel_failure(detail: str, *, oom_killed: bool) -> SandboxError:
    """A sandbox death, classified. Memory kill and plain crash are not the same thing."""
    if oom_killed:
        return SandboxError(
            ErrorKind.RESOURCE_LIMIT,
            "The sandbox was killed after exceeding its memory limit.",
            detail,
        )
    return SandboxError(
        ErrorKind.CONTAINER_ERROR,
        "The sandbox kernel stopped responding; the run's sandbox has been torn down.",
        detail,
    )


def docker_reachable(docker_bin: str, timeout: float = 15.0) -> bool:
    """Whether a real container can be started right now.

    `docker version` needs the socket for the server half, which is exactly the call
    that fails with `permission denied … /var/run/docker.sock` for a process that is
    not in the `docker` group. So this probe, and not a `shutil.which`, is what routes
    an unreachable socket to the fallback.
    """
    try:
        probe = subprocess.run(
            [docker_bin, "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


class SubprocessBackend:
    """The dev fallback: the same kernel, in a plain process, with the repository's venv.

    Weaker than Docker on purpose and by construction — there is no network namespace,
    no read-only root and no memory limit that a plain process can be given. It exists
    so the sandbox has one interface on a machine where `/var/run/docker.sock` cannot be
    reached, and so the interface itself is testable without a container.

    Its library set is the venv's, not the image's. `pandas` is not installed in
    `backend/venv`, so code that imports it fails here and succeeds in Docker. That
    difference is real, and it is stated rather than tested as if it were parity.
    """

    name = "subprocess"

    def __init__(
        self,
        spec: ContainerSpec,
        *,
        python: str | None = None,
        kernel_path: Path | None = None,
    ):
        self._spec = spec
        self._python = python or sys.executable
        self._kernel_path = Path(kernel_path) if kernel_path else KERNEL_PATH
        self._process: subprocess.Popen | None = None

    # -- lifecycle ---------------------------------------------------------- #

    def start(self) -> None:
        if self._process is not None:
            return
        for directory in (
            self._spec.host_ipc_dir,
            self._spec.host_data_dir,
            self._spec.host_work_dir,
            self._spec.host_output_dir,
        ):
            os.makedirs(directory, exist_ok=True)
        if os.path.exists(self._spec.host_socket_path):
            os.unlink(self._spec.host_socket_path)

        log = open(os.path.join(self._spec.host_root, "kernel.log"), "ab")
        try:
            self._process = subprocess.Popen(
                [
                    self._python,
                    str(self._kernel_path),
                    "--socket", self._spec.host_socket_path,
                    "--data-dir", self._spec.host_data_dir,
                    "--work-dir", self._spec.host_work_dir,
                    "--output-dir", self._spec.host_output_dir,
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
        finally:
            log.close()
        try:
            _await_socket(self._spec.host_socket_path, self._process, self._kernel_log())
        except SandboxError:
            self.stop()
            raise

    def stop(self) -> None:
        process, self._process = self._process, None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if os.path.exists(self._spec.host_socket_path):
            os.unlink(self._spec.host_socket_path)

    def is_alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    # -- jobs --------------------------------------------------------------- #

    def run(self, request: JobRequest, timeout: float) -> KernelResponse:
        if not self.is_alive():
            raise kernel_failure("the sandbox process is not running", oom_killed=False)
        try:
            reply = send_request(self._spec.host_socket_path, request.to_payload(), timeout)
        except TimeoutError as exc:
            self.stop()
            raise SandboxError(
                ErrorKind.TIMEOUT,
                "The sandbox kernel did not answer in time; the run's sandbox has been torn down.",
                str(exc),
            ) from exc
        except OSError as exc:
            detail = f"{exc} {self._kernel_log()}".strip()
            self.stop()
            raise kernel_failure(detail, oom_killed=False) from exc
        return KernelResponse.from_payload(reply)

    def collect_outputs(self) -> list[tuple[str, bytes]]:
        return _collect_files(self._spec.host_output_dir)

    # -- helpers ------------------------------------------------------------ #

    def _kernel_log(self) -> str:
        path = os.path.join(self._spec.host_root, "kernel.log")
        if not os.path.exists(path):
            return ""
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8", "replace")[-2000:]


def _await_socket(socket_path: str, process: subprocess.Popen, log: str, budget: float = 15.0):
    """Wait for the kernel to create its socket, or fail with what it printed."""
    import time

    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        if os.path.exists(socket_path):
            return
        if process.poll() is not None:
            raise SandboxError(
                ErrorKind.CONTAINER_ERROR,
                "The sandbox kernel exited before it was ready.",
                log or f"exit code {process.returncode}",
            )
        time.sleep(0.02)
    raise SandboxError(
        ErrorKind.CONTAINER_ERROR,
        "The sandbox kernel did not become ready in time.",
        log,
    )


def _collect_files(root: str) -> list[tuple[str, bytes]]:
    """Every file under `root`, as `(relative posix path, contents)`, sorted."""
    if not os.path.isdir(root):
        return []
    collected: list[tuple[str, bytes]] = []
    for dirpath, _directories, names in os.walk(root):
        for name in names:
            full = os.path.join(dirpath, name)
            with open(full, "rb") as handle:
                relative = os.path.relpath(full, root).replace(os.sep, "/")
                collected.append((relative, handle.read()))
    return sorted(collected)
