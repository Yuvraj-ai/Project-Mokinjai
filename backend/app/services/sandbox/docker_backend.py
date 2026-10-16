"""The Docker isolation backend: the kernel in a container (ADR-010).

Drives the `docker` CLI through `subprocess` rather than the docker Python SDK. Two
reasons. It is not a new dependency, and the repository root contains a `docker/`
directory of Dockerfiles, so `import docker` with the root on `sys.path` resolves to
that directory as a namespace package — an SDK import would be silently shadowed there.

Isolation is entirely in the flags, so they are built in one place
(`DockerBackend._run_command`) where a reader can see all of them at once.
"""

import os
import shutil
import subprocess
import tarfile
import time
from datetime import datetime, timezone

from app.logging import logger
from app.services.sandbox.backends import ContainerSpec, _collect_files, kernel_failure
from app.services.sandbox.errors import ErrorKind, SandboxError
from app.services.sandbox.protocol import JobRequest, KernelResponse, send_request

SANDBOX_ROOT = "/app"
DATA_DIR = "/app/data"
WORK_DIR = "/app/work"
OUTPUT_DIR = "/app/output"
IPC_DIR = "/app/ipc"
KERNEL_PATH_IN_IMAGE = "/app/kernel.py"
SWEEP_LABEL = "mokinjay.sandbox=1"


class DockerBackend:
    """Runs the kernel in one container per run."""

    name = "docker"

    def __init__(
        self,
        spec: ContainerSpec,
        *,
        docker_bin: str = "docker",
        command_timeout: float = 60.0,
    ):
        self._spec = spec
        self._docker_bin = docker_bin
        self._command_timeout = command_timeout
        self._container_id: str | None = None

    # -- lifecycle ---------------------------------------------------------- #

    def start(self) -> None:
        if self._container_id is not None:
            return
        self._require_image()

        # The second of the four bounds that keep a leaked container from surviving a
        # parent that died without calling stop(). The first is the container's own
        # `sleep <max_run_seconds>`, which stops it; `--rm` then removes it. This
        # catches the window in which that `sleep` has not expired yet.
        sweep(self._docker_bin, self._spec.max_run_seconds)

        os.makedirs(self._spec.host_ipc_dir, exist_ok=True)
        os.makedirs(self._spec.host_data_dir, exist_ok=True)

        result = subprocess.run(
            self._run_command(),
            capture_output=True,
            text=True,
            timeout=self._command_timeout,
        )
        if result.returncode != 0:
            raise SandboxError(
                ErrorKind.CONTAINER_ERROR,
                "The sandbox container could not be created.",
                (result.stderr or result.stdout).strip(),
            )
        self._container_id = result.stdout.strip()
        logger.info(
            f"Sandbox container {self._container_id[:12]} up for {self._spec.name}"
        )

        exec_result = subprocess.run(
            [
                self._docker_bin,
                "exec",
                "-d",
                self._container_id,
                "python",
                KERNEL_PATH_IN_IMAGE,
                "--socket",
                f"{IPC_DIR}/{self._spec.socket_name}",
                "--data-dir",
                DATA_DIR,
                "--work-dir",
                WORK_DIR,
                "--output-dir",
                OUTPUT_DIR,
            ],
            capture_output=True,
            text=True,
            timeout=self._command_timeout,
        )
        if exec_result.returncode != 0:
            self.stop()
            raise SandboxError(
                ErrorKind.CONTAINER_ERROR,
                "The sandbox kernel could not be started.",
                (exec_result.stderr or exec_result.stdout).strip(),
            )

        try:
            self._await_socket()
        except SandboxError:
            self.stop()
            raise

    def stop(self) -> None:
        container_id, self._container_id = self._container_id, None
        if container_id is not None:
            subprocess.run(
                [self._docker_bin, "rm", "-f", container_id],
                capture_output=True,
                text=True,
                timeout=self._command_timeout,
            )
        if os.path.exists(self._spec.host_socket_path):
            os.unlink(self._spec.host_socket_path)

    def is_alive(self) -> bool:
        if self._container_id is None:
            return False
        result = subprocess.run(
            [self._docker_bin, "inspect", "--format", "{{.State.Running}}", self._container_id],
            capture_output=True,
            text=True,
            timeout=self._command_timeout,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    # -- jobs --------------------------------------------------------------- #

    def run(self, request: JobRequest, timeout: float) -> KernelResponse:
        if not self.is_alive():
            raise kernel_failure("the sandbox container is not running", oom_killed=False)
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
            oom_killed = self._oom_killed()
            self.stop()
            raise kernel_failure(str(exc), oom_killed=oom_killed) from exc
        return KernelResponse.from_payload(reply)

    def collect_outputs(self) -> list[tuple[str, bytes]]:
        """This job's files, pulled out of the output tmpfs.

        ADR-010 makes `/app/output` a tmpfs, and `docker cp` cannot copy from tmpfs mounts
        because it resolves against host overlay layers rather than the container's mount
        namespace. We extract files using a tar stream via `docker exec`.
        """
        if self._container_id is None:
            return []
        staging = os.path.join(self._spec.host_root, "collected")
        shutil.rmtree(staging, ignore_errors=True)
        os.makedirs(staging, exist_ok=True)
        try:
            tar_proc = subprocess.Popen(
                [self._docker_bin, "exec", self._container_id, "tar", "-C", OUTPUT_DIR, "-cf", "-", "."],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            with tarfile.open(fileobj=tar_proc.stdout, mode="r|*") as archive:
                archive.extractall(staging, filter="data")
            tar_proc.wait(timeout=self._command_timeout)
        except Exception as exc:
            logger.warning(f"Collecting sandbox output failed: {exc}")
            return []
        return _collect_files(staging)

    # -- the flags ---------------------------------------------------------- #

    def _run_command(self) -> list[str]:
        """Every isolation flag, in one place, in one order."""
        command = [
            self._docker_bin, "run", "-d", "--rm",
            "--name", self._spec.name,
            "--label", SWEEP_LABEL,
            *[f"--label={key}={value}" for key, value in self._spec.labels.items()],
            "--memory", self._spec.memory,
            "--cpus", self._spec.cpus,
            "--network", self._spec.network,
            "--user", self._spec.user,
            "--tmpfs", f"{WORK_DIR}:size={self._spec.work_tmpfs_mb}m,mode=1777",
            "--tmpfs", f"{OUTPUT_DIR}:size={self._spec.output_tmpfs_mb}m,mode=1777",
            "-v", f"{self._spec.host_ipc_dir}:{IPC_DIR}:rw",
            "-v", f"{self._spec.host_data_dir}:{DATA_DIR}:ro",
            "--workdir", WORK_DIR,
        ]
        if self._spec.read_only:
            command.append("--read-only")
        # The container's main process. Its exit is what bounds the container's life
        # when nothing else can: `--rm` then removes it.
        command += [self._spec.image, "sleep", str(self._spec.max_run_seconds)]
        return command

    # -- helpers ------------------------------------------------------------ #

    def _require_image(self) -> None:
        result = subprocess.run(
            [self._docker_bin, "image", "inspect", self._spec.image],
            capture_output=True,
            text=True,
            timeout=self._command_timeout,
        )
        if result.returncode != 0:
            raise SandboxError(
                ErrorKind.IMAGE_MISSING,
                f"The sandbox image {self._spec.image} is not built. Build it with: "
                f"docker build -f docker/Dockerfile.sandbox -t {self._spec.image} .",
                (result.stderr or result.stdout).strip(),
            )

    def _await_socket(self, budget: float = 30.0) -> None:
        deadline = time.monotonic() + budget
        while time.monotonic() < deadline:
            if not self.is_alive():
                raise SandboxError(
                    ErrorKind.CONTAINER_ERROR,
                    "The sandbox container exited unexpectedly during startup.",
                    self._container_logs(),
                )
            if os.path.exists(self._spec.host_socket_path):
                return
            time.sleep(0.05)
        raise SandboxError(
            ErrorKind.CONTAINER_ERROR,
            "The sandbox kernel did not become ready in time.",
            self._container_logs(),
        )

    def _oom_killed(self) -> bool:
        if self._container_id is None:
            return False
        result = subprocess.run(
            [self._docker_bin, "inspect", "--format", "{{.State.OOMKilled}}", self._container_id],
            capture_output=True,
            text=True,
            timeout=self._command_timeout,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def _container_logs(self) -> str:
        if self._container_id is None:
            return ""
        result = subprocess.run(
            [self._docker_bin, "logs", "--tail", "40", self._container_id],
            capture_output=True,
            text=True,
            timeout=self._command_timeout,
        )
        return (result.stdout + result.stderr).strip()


def sweep(docker_bin: str, ttl_seconds: int, *, timeout: float = 30.0) -> int:
    """Remove sandbox containers older than the maximum run length.

    Removes only containers carrying `mokinjay.sandbox=1`: a container this project did
    not create is never a candidate.
    """
    try:
        listed = subprocess.run(
            [
                docker_bin, "ps", "-aq",
                "--filter", f"label={SWEEP_LABEL}",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    ids = listed.stdout.split()
    if not ids:
        return 0
    try:
        inspected = subprocess.run(
            [docker_bin, "inspect", "--format", "{{.Id}} {{.State.StartedAt}}", *ids],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return 0
    stale_ids = []
    now = datetime.now(timezone.utc)
    for line in inspected.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        cid, started_at_str = parts
        try:
            iso_str = started_at_str
            if iso_str.endswith("Z"):
                iso_str = iso_str[:-1] + "+00:00"
            if "." in iso_str:
                base, rest = iso_str.split(".")
                tz_idx = max(rest.find("+"), rest.find("-"))
                frac, tz = (rest[:6], rest[tz_idx:]) if tz_idx != -1 else (rest[:6], "+00:00")
                iso_str = f"{base}.{frac}{tz}"
            dt = datetime.fromisoformat(iso_str)
            age = (now - dt).total_seconds()
            if age >= ttl_seconds:
                stale_ids.append(cid)
        except Exception:
            continue

    if not stale_ids:
        return 0
    subprocess.run(
        [docker_bin, "rm", "-f", *stale_ids],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    logger.info(f"Swept {len(stale_ids)} stale sandbox container(s)")
    return len(stale_ids)

