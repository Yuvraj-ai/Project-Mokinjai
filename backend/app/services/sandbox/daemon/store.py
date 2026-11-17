"""The daemon's session registry, its tar boundary, and its disk hygiene.

A session is one temp root plus one `DockerBackend` — the same backend the local API
uses. Nothing above the backend is imported: the daemon has no notion of a tool call.
"""

import os
import re
import shutil
import subprocess
import tarfile
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import get_settings
from app.logging import logger
from app.services.sandbox.backends import ContainerSpec, IsolationBackend
from app.services.sandbox.docker_backend import DockerBackend
from app.services.sandbox.errors import SandboxError
from app.services.sandbox.protocol import JobRequest

SESSIONS_ROOT = Path("/data/sessions")
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# shortcut: two 2 GiB tiers fit an 8 GiB machine; revisit if tiers change.
MAX_SESSIONS = 2


class InvalidSession(Exception):
    """A request that cannot safely become a path: bad id or bad tar member."""


class AdmissionFull(Exception):
    """The machine already runs the maximum number of sessions."""


class UnknownSession(Exception):
    """A job or output request named a session this daemon does not hold."""


class JobInProgress(Exception):
    """The same job id is still running; the caller should retry later."""


# A cached reply is the whole KernelResponse payload. This sentinel marks a job that
# is running, so a racing retry gets 409 instead of starting a second container.
_IN_PROGRESS = object()
MAX_CACHED_JOBS = 100


@dataclass
class RemoteSession:
    session_id: str
    root: Path
    backend: IsolationBackend
    created_at: float
    max_run_seconds: int
    jobs: dict[str, dict] = field(default_factory=dict)
    # Guards `jobs` only. The store's own lock guards the registry.
    lock: threading.Lock = field(default_factory=threading.Lock)


def validate_session_id(session_id: str) -> None:
    """The id becomes a directory name and a container name, so it is checked first."""
    if not SESSION_ID_PATTERN.fullmatch(session_id or ""):
        raise InvalidSession("session_id must match ^[A-Za-z0-9_-]{1,64}$")


def _extract_tar(archive: tarfile.TarFile, destination: Path, limit: int) -> None:
    """Extract member by member: a signed caller is still a caller."""
    total = 0
    for member in archive.getmembers():
        name = member.name
        if name.startswith("/") or ".." in Path(name).parts:
            raise InvalidSession(f"refusing a tar member named {name!r}")
        if member.issym() or member.islnk():
            raise InvalidSession(f"refusing a link in the upload: {name!r}")
        target = destination / name
        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        if not member.isfile():
            raise InvalidSession(f"refusing a special file in the upload: {name!r}")
        total += member.size
        if total > limit:
            raise InvalidSession(f"the upload exceeds the {limit} byte limit")
        target.parent.mkdir(parents=True, exist_ok=True)
        source = archive.extractfile(member)
        if source is None:
            raise InvalidSession(f"unreadable tar member {name!r}")
        target.write_bytes(source.read())


def _container_spec(session_id: str, root: Path, fields: dict) -> ContainerSpec:
    """Build the spec here: host paths never arrive over the network."""
    return ContainerSpec(
        name=session_id,
        image=str(fields.get("image") or "mokinjay-sandbox:1"),
        memory=str(fields.get("memory") or "256m"),
        cpus=str(fields.get("cpus") or "0.5"),
        user=str(fields.get("user") or "1000:1000"),
        network=str(fields.get("network") or "none"),
        read_only=bool(fields.get("read_only", True)),
        host_root=str(root),
        output_tmpfs_mb=int(fields.get("output_tmpfs_mb") or 64),
        work_tmpfs_mb=int(fields.get("work_tmpfs_mb") or 64),
        max_run_seconds=int(fields.get("max_run_seconds") or 1800),
    )


def _container_ownership(user: str) -> tuple[int, int] | None:
    """`"1000:1000"` → `(1000, 1000)`, or None when it is not numeric."""
    uid, _, gid = str(user).partition(":")
    try:
        return int(uid), int(gid or uid)
    except ValueError:
        return None


def _own_for_container(path: Path, user: str) -> None:
    """Give the bind-mounted directory to the uid the container runs as.

    The daemon usually runs as root (it needs the Docker socket), while the container
    runs as `1000:1000` and must create the kernel socket and log inside `ipc/`.
    Skip when the daemon is not root: then it already owns the directory, as it does
    in local development.
    """
    ids = _container_ownership(user)
    if ids is None or os.geteuid() != 0:
        return
    os.chown(path, *ids)


class SessionStore:
    """The registry and everything that touches the host filesystem under it."""

    def __init__(self) -> None:
        self._sessions: dict[str, RemoteSession] = {}
        self._lock = threading.Lock()
        # Creation is serialised: two creates for one id must not both start a backend.
        self._create_lock = threading.Lock()
        self._admission = threading.Semaphore(MAX_SESSIONS)

    def get(self, session_id: str) -> RemoteSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def create(
        self,
        session_id: str,
        spec_fields: dict,
        archive: tarfile.TarFile,
    ) -> tuple[RemoteSession, bool]:
        """Create a session, or return the registered one unchanged."""
        validate_session_id(session_id)
        with self._create_lock:
            existing = self.get(session_id)
            if existing is not None:
                return existing, False

            if not self._admission.acquire(blocking=False):
                raise AdmissionFull("the sandbox host is at capacity")

            root = SESSIONS_ROOT / session_id
            max_run_seconds = int(spec_fields.get("max_run_seconds") or 1800)
            try:
                self.prune_stale(max_run_seconds)
                shutil.rmtree(root, ignore_errors=True)
                (root / "data").mkdir(parents=True, exist_ok=True)
                _extract_tar(
                    archive,
                    root / "data",
                    get_settings().STORAGE_MAX_UPLOAD_BYTES,
                )
                ipc = root / "ipc"
                ipc.mkdir(parents=True, exist_ok=True)
                _own_for_container(ipc, str(spec_fields.get("user") or "1000:1000"))
                self._remove_container(session_id)
                backend = DockerBackend(_container_spec(session_id, root, spec_fields))
                backend.start()
            except Exception:
                self._admission.release()
                shutil.rmtree(root, ignore_errors=True)
                raise

            session = RemoteSession(
                session_id=session_id,
                root=root,
                backend=backend,
                created_at=time.time(),
                max_run_seconds=max_run_seconds,
            )
            with self._lock:
                self._sessions[session_id] = session
            return session, True

    def run_job(
        self,
        session_id: str,
        job_id: str,
        request: JobRequest,
        timeout: float,
    ) -> dict:
        """Run one job, or replay the reply this job id already produced."""
        session = self.get(session_id)
        if session is None:
            raise UnknownSession(session_id)

        with session.lock:
            cached = session.jobs.get(job_id)
            if cached is _IN_PROGRESS:
                raise JobInProgress(job_id)
            if cached is not None:
                return cached
            session.jobs[job_id] = _IN_PROGRESS
            if len(session.jobs) > MAX_CACHED_JOBS:
                for key in list(session.jobs):
                    if session.jobs[key] is not _IN_PROGRESS:
                        session.jobs.pop(key)
                        break

        try:
            response = session.backend.run(request, timeout)
        except Exception:
            with session.lock:
                session.jobs.pop(job_id, None)
            raise

        payload = asdict(response)
        with session.lock:
            session.jobs[job_id] = payload
        return payload

    def delete(self, session_id: str) -> bool:
        """Stop and clean up. Deleting an unknown session is not an error."""
        validate_session_id(session_id)
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        try:
            session.backend.stop()
        except SandboxError:
            logger.warning(f"Sandbox session {session_id} failed to stop cleanly")
        finally:
            self._admission.release()
            shutil.rmtree(session.root, ignore_errors=True)
        return True

    def prune_stale(self, max_run_seconds: int) -> None:
        """Remove leaked roots: `close()` never runs if the caller dies."""
        if not SESSIONS_ROOT.is_dir():
            return
        cutoff = time.time() - (max_run_seconds + 3600)
        with self._lock:
            registered = set(self._sessions)
        for child in SESSIONS_ROOT.iterdir():
            if child.name in registered:
                continue
            try:
                if child.is_dir() and child.stat().st_mtime < cutoff:
                    shutil.rmtree(child, ignore_errors=True)
            except OSError:
                logger.warning(f"Could not inspect a stale session root {child!r}")

    @staticmethod
    def _remove_container(session_id: str) -> None:
        """A registry lost to a restart must not collide with a live container."""
        try:
            subprocess.run(
                [get_settings().SANDBOX_DOCKER_BIN, "rm", "-f", session_id],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            logger.warning(f"Could not remove a leftover container named {session_id!r}")
