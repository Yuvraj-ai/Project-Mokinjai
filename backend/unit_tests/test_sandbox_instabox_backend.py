"""The API-side client for the remote daemon, driven through httpx.MockTransport.

No test opens a socket. The point of the suite is the contract with the daemon: one
signed request per call, one retry on transport failure with the same job id, and no
retry when the host has already answered.
"""

import io
import json
import tarfile
import time

import pytest
from httpx import ConnectError, MockTransport, Response

from app.services.sandbox.daemon.auth import verify
from app.services.sandbox.errors import ErrorKind, SandboxError
from app.services.sandbox.instabox_backend import InstaboxBackend
from app.services.sandbox.protocol import JobRequest

SECRET = "test-daemon-secret"
TOKEN = "ibp_test"


def make_spec(tmp_path):
    from app.services.sandbox.backends import ContainerSpec

    return ContainerSpec(
        name="mokinjay-sandbox-run1",
        image="mokinjay-sandbox:1",
        memory="256m",
        cpus="0.5",
        user="1000:1000",
        network="none",
        read_only=True,
        host_root=str(tmp_path),
        output_tmpfs_mb=64,
        work_tmpfs_mb=64,
        max_run_seconds=60,
    )


def backend(tmp_path, handler, token=TOKEN):
    return InstaboxBackend(
        make_spec(tmp_path),
        base_url="http://daemon",
        token=token,
        secret=SECRET,
        transport=MockTransport(handler),
    )


def reply(status=200, payload=None, **headers):
    return Response(status, json=payload if payload is not None else {}, headers=headers)


@pytest.fixture
def request_payload():
    return JobRequest(kind="python", timeout=5.0, code="1+2")


def test_start_uploads_the_staged_files(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "notes.txt").write_bytes(b"hello")
    seen = []

    def handler(request):
        seen.append(request)
        return reply(201, {"session_id": "mokinjay-sandbox-run1"})

    client = backend(tmp_path, handler)
    client.start()

    assert len(seen) == 1
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/sessions"
    assert b"notes.txt" in seen[0].read()
    assert b"hello" in seen[0].read()


def test_start_is_idempotent(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        return reply(201, {})

    client = backend(tmp_path, handler)
    client.start()
    client.start()

    assert len(seen) == 1


def test_run_returns_a_kernel_response(tmp_path, request_payload):
    def handler(_request):
        return reply(200, {"status": "ok", "stdout": "hi\n", "result": 3})

    response = backend(tmp_path, handler).run(request_payload, timeout=5.0)

    assert response.status == "ok"
    assert response.result == 3


def test_run_retries_once_on_connect_error_then_succeeds(tmp_path, request_payload):
    calls = []

    def handler(request):
        calls.append(json.loads(request.read())["job_id"])
        if len(calls) == 1:
            raise ConnectError("waking up")
        return reply(200, {"status": "ok"})

    response = backend(tmp_path, handler).run(request_payload, timeout=5.0)

    assert response.status == "ok"
    assert len(calls) == 2
    assert calls[0] == calls[1]


def test_run_does_not_retry_on_409(tmp_path, request_payload):
    calls = []

    def handler(_request):
        calls.append(1)
        return reply(409, {"detail": "machine_cooldown"})

    with pytest.raises(SandboxError) as caught:
        backend(tmp_path, handler).run(request_payload, timeout=5.0)

    assert len(calls) == 1
    assert caught.value.info.kind == ErrorKind.BACKEND_UNAVAILABLE.value


def test_run_does_not_retry_on_503(tmp_path, request_payload):
    calls = []

    def handler(_request):
        calls.append(1)
        return reply(503, {"detail": "stopped"})

    with pytest.raises(SandboxError) as caught:
        backend(tmp_path, handler).run(request_payload, timeout=5.0)

    assert len(calls) == 1
    assert caught.value.info.kind == ErrorKind.BACKEND_UNAVAILABLE.value


def test_a_502_typed_error_becomes_a_sandbox_error(tmp_path, request_payload):
    def handler(_request):
        return reply(502, {"kind": "container_error", "message": "boom", "detail": "trace"})

    with pytest.raises(SandboxError) as caught:
        backend(tmp_path, handler).run(request_payload, timeout=5.0)

    assert caught.value.info.kind == "container_error"
    assert caught.value.info.message == "boom"
    assert caught.value.info.detail == "trace"


def test_collect_outputs_unpacks_the_tar(tmp_path):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo("chart.png")
        info.size = 3
        archive.addfile(info, io.BytesIO(b"png"))
    payload = buffer.getvalue()

    def handler(_request):
        return Response(200, content=payload, headers={"content-type": "application/x-tar"})

    assert backend(tmp_path, handler).collect_outputs() == [("chart.png", b"png")]


def test_stop_is_idempotent_and_tolerates_404(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.method)
        return reply(404, {"detail": "unknown session"})

    client = backend(tmp_path, handler)
    client._started = True
    client.stop()
    client.stop()

    assert calls == ["DELETE"]


def test_the_request_is_signed(tmp_path, request_payload):
    verified = []

    def handler(request):
        verified.append(
            verify(SECRET, request.headers.get("X-Mokinjay-Signature"), request.read(), now=int(time.time()))
        )
        return reply(200, {"status": "ok"})

    backend(tmp_path, handler).run(request_payload, timeout=5.0)

    assert verified == [None]


def test_the_token_is_sent(tmp_path, request_payload):
    seen = []

    def handler(request):
        seen.append(request.headers.get("Authorization"))
        return reply(200, {"status": "ok"})

    backend(tmp_path, handler).run(request_payload, timeout=5.0)

    assert seen == [f"Bearer {TOKEN}"]


def test_no_authorization_header_is_sent_without_a_token(tmp_path, request_payload):
    seen = []

    def handler(request):
        seen.append(request.headers.get("Authorization"))
        return reply(200, {"status": "ok"})

    backend(tmp_path, handler, token="").run(request_payload, timeout=5.0)

    assert seen == [None]


def test_a_tar_above_the_direct_limit_is_uploaded_in_parts(tmp_path, monkeypatch):
    from app.services.sandbox import instabox_backend as module

    monkeypatch.setattr(module, "DIRECT_UPLOAD_LIMIT", 200)
    monkeypatch.setattr(module, "UPLOAD_CHUNK_BYTES", 4096)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "big.bin").write_bytes(b"x" * 5000)
    expected = module._tar_directory(str(tmp_path / "data"))
    calls = []

    def handler(request):
        body = request.read()
        calls.append((request.method, request.url.path, request.url.params.get("offset"), body))
        if request.url.path.endswith("/sessions"):
            return reply(201, {"session_id": "mokinjay-sandbox-run1"})
        return Response(204)

    backend(tmp_path, handler).start()

    assert calls[0][0:3] == ("POST", "/sessions", None)
    parts = [call for call in calls if call[1].endswith("/files")]
    assert [int(call[2]) for call in parts] == [0, 4096, 8192]
    assert b"".join(call[3] for call in parts) == expected
    assert calls[-1][0:3] == ("POST", "/sessions/mokinjay-sandbox-run1/files/finalize", None)


def test_a_failed_part_deletes_the_remote_session(tmp_path, monkeypatch):
    from app.services.sandbox import instabox_backend as module

    monkeypatch.setattr(module, "DIRECT_UPLOAD_LIMIT", 200)
    monkeypatch.setattr(module, "UPLOAD_CHUNK_BYTES", 4096)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "big.bin").write_bytes(b"x" * 5000)
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/sessions"):
            return reply(201, {"session_id": "mokinjay-sandbox-run1"})
        if request.url.path.endswith("/files"):
            return reply(500, {"detail": "boom"})
        return Response(204)

    with pytest.raises(SandboxError):
        backend(tmp_path, handler).start()

    assert ("DELETE", "/sessions/mokinjay-sandbox-run1") in calls
