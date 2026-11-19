"""The HTTP isolation backend: the API's half of the remote sandbox contract.

It implements the same `IsolationBackend` Protocol as `DockerBackend`, so
`SandboxSession` is unchanged. What differs is the wire: staged files go up as a tar
at `start()`, jobs go to the daemon with a client-generated id, and outputs come back
as a streamed tar.
"""

import io
import json
import tarfile
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import quote

import httpx

from app.logging import logger
from app.services.sandbox.backends import ContainerSpec
from app.services.sandbox.daemon.auth import sign
from app.services.sandbox.errors import ErrorKind, SandboxError
from app.services.sandbox.protocol import JobRequest, KernelResponse

TRANSPORT_FAILURES = (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError)
RETRY_BACKOFF_SECONDS = 0.5
UNAVAILABLE_MESSAGE = "The execution engine is restarting."
# The InstaBox proxy rejects bodies above 32 MiB. Keep the direct multipart create
# under that, and send anything larger as parts of 16 MiB.
DIRECT_UPLOAD_LIMIT = 31 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 16 * 1024 * 1024


def _empty_tar() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w"):
        pass
    return buffer.getvalue()


def _tar_directory(root: str) -> bytes:
    """A tar of `root`, or a valid empty tar when there is nothing to stage."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        if Path(root).is_dir():
            for path in sorted(Path(root).rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=str(path.relative_to(root)))
    return buffer.getvalue()


def _spec_fields(spec: ContainerSpec) -> dict:
    """Logical fields only. Host paths are the daemon's business."""
    return {
        "image": spec.image,
        "memory": spec.memory,
        "cpus": spec.cpus,
        "user": spec.user,
        "network": spec.network,
        "read_only": spec.read_only,
        "output_tmpfs_mb": spec.output_tmpfs_mb,
        "work_tmpfs_mb": spec.work_tmpfs_mb,
        "max_run_seconds": spec.max_run_seconds,
    }


class InstaboxBackend:
    """One remote session, reached over the daemon's signed HTTP API."""

    name = "instabox"

    def __init__(
        self,
        spec: ContainerSpec,
        *,
        base_url: str,
        token: str,
        secret: str,
        timeout_grace: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._spec = spec
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._secret = secret
        self._timeout_grace = timeout_grace
        self._started = False
        # A public-only port has no InstaBox bearer token. httpx refuses an empty
        # header value, so omit the header entirely rather than send "Bearer ".
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._client = httpx.Client(headers=headers, transport=transport)

    # -- lifecycle ---------------------------------------------------------- #

    def start(self) -> None:
        if self._started:
            return
        payload = _tar_directory(self._spec.host_data_dir)
        path = f"/sessions/{quote(self._spec.name, safe='')}"
        response = self._send(
            "POST",
            "/sessions",
            data={"session_id": self._spec.name, "spec": json.dumps(_spec_fields(self._spec))},
            files={
                "data": (
                    "data.tar",
                    payload if len(payload) <= DIRECT_UPLOAD_LIMIT else _empty_tar(),
                    "application/x-tar",
                )
            },
            timeout=httpx.Timeout(connect=10, write=120, read=120, pool=10),
        )
        self._raise_for_status(response)

        if len(payload) > DIRECT_UPLOAD_LIMIT:
            try:
                for offset in range(0, len(payload), UPLOAD_CHUNK_BYTES):
                    part = payload[offset:offset + UPLOAD_CHUNK_BYTES]
                    self._raise_for_status(
                        self._send(
                            "POST",
                            f"{path}/files?offset={offset}",
                            content=part,
                            timeout=httpx.Timeout(connect=10, write=60, read=60, pool=10),
                        )
                    )
                self._raise_for_status(
                    self._send(
                        "POST",
                        f"{path}/files/finalize",
                        timeout=httpx.Timeout(connect=10, write=30, read=120, pool=10),
                    )
                )
            except Exception:
                # The remote session exists even though this client never became usable.
                self._delete_remote(path)
                raise
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        self._delete_remote(f"/sessions/{quote(self._spec.name, safe='')}")

    def _delete_remote(self, path: str) -> None:
        try:
            response = self._send(
                "DELETE",
                path,
                timeout=httpx.Timeout(connect=10, write=30, read=30, pool=10),
            )
            if response.status_code != 404:
                self._raise_for_status(response)
        except (httpx.HTTPError, SandboxError):
            # Close cannot fail the run: the daemon prunes leaked roots itself.
            logger.warning(f"Could not close sandbox session {self._spec.name}")

    def is_alive(self) -> bool:
        if not self._started:
            return False
        try:
            response = self._send(
                "GET",
                f"/sessions/{quote(self._spec.name, safe='')}",
                timeout=httpx.Timeout(connect=10, write=30, read=30, pool=10),
            )
            self._raise_for_status(response)
            return bool(response.json().get("alive"))
        except (httpx.HTTPError, SandboxError, ValueError):
            return False

    # -- work --------------------------------------------------------------- #

    def run(self, request: JobRequest, timeout: float) -> KernelResponse:
        job_id = str(uuid.uuid4())
        payload = {"job_id": job_id, "request": request.to_payload()}
        read_timeout = timeout + self._timeout_grace
        attempt = lambda: self._send(  # noqa: E731 - one expression, two calls
            "POST",
            f"/sessions/{quote(self._spec.name, safe='')}/jobs",
            json=payload,
            timeout=httpx.Timeout(connect=10, write=60, read=read_timeout, pool=10),
        )
        try:
            try:
                response = attempt()
            except TRANSPORT_FAILURES:
                time.sleep(RETRY_BACKOFF_SECONDS)
                response = attempt()
        except TRANSPORT_FAILURES:
            raise SandboxError(ErrorKind.BACKEND_UNAVAILABLE, "The sandbox host did not answer.")
        self._raise_for_status(response)
        return KernelResponse.from_payload(response.json())

    def collect_outputs(self) -> list[tuple[str, bytes]]:
        url = f"{self._base_url}/sessions/{quote(self._spec.name, safe='')}/outputs"
        headers = {"X-Mokinjay-Signature": sign(self._secret, int(time.time()), b"")}
        collected: list[tuple[str, bytes]] = []
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            temporary = handle.name
        try:
            with self._client.stream(
                "GET",
                url,
                headers=headers,
                timeout=httpx.Timeout(connect=10, write=30, read=120, pool=10),
            ) as response:
                if response.status_code >= 400:
                    response.read()
                    self._raise_for_status(response)
                with open(temporary, "wb") as sink:
                    for chunk in response.iter_bytes(1024 * 1024):
                        sink.write(chunk)
            with tarfile.open(temporary, mode="r:*") as archive:
                for member in archive.getmembers():
                    name = member.name
                    if name.startswith("/") or ".." in Path(name).parts:
                        raise SandboxError(
                            ErrorKind.CONTAINER_ERROR,
                            "The sandbox host returned an unsafe output path.",
                            name,
                        )
                    if not member.isfile():
                        continue
                    source = archive.extractfile(member)
                    if source is not None:
                        collected.append((name, source.read()))
        finally:
            Path(temporary).unlink(missing_ok=True)
        return collected

    # -- transport ---------------------------------------------------------- #

    def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        request = self._client.build_request(method, f"{self._base_url}{path}", **kwargs)
        body = request.read()
        request.headers["X-Mokinjay-Signature"] = sign(self._secret, int(time.time()), body)
        return self._client.send(request)

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if 200 <= response.status_code < 300:
            return
        if response.status_code in (409, 503):
            raise SandboxError(ErrorKind.BACKEND_UNAVAILABLE, UNAVAILABLE_MESSAGE)
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if isinstance(payload, dict) and payload.get("kind"):
            raise SandboxError(
                payload["kind"],
                payload.get("message") or "The sandbox host refused the request.",
                payload.get("detail"),
            )
        raise SandboxError(
            ErrorKind.CONTAINER_ERROR,
            f"The sandbox host answered {response.status_code}.",
        )
