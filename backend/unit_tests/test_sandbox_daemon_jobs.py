"""One job per request, keyed by a client-generated id.

Agent code is not idempotent, so a retry must never start a second container for the
same call. The cache lives in memory: a daemon restart loses it and a retry re-runs,
which is the documented, bounded failure.
"""

import io
import json
import tarfile
import time
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.sandbox.daemon import app as daemon_app
from app.services.sandbox.daemon import store as store_module
from app.services.sandbox.daemon.auth import sign
from app.services.sandbox.errors import SandboxError
from app.services.sandbox.protocol import JobRequest, KernelResponse

SECRET = "test-daemon-secret"


class FakeBackend:
    instances: list["FakeBackend"] = []

    def __init__(self, spec):
        self.spec = spec
        self.calls: list[tuple[JobRequest, float]] = []
        self.started = False
        FakeBackend.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def is_alive(self):
        return self.started

    def run(self, request, timeout):
        self.calls.append((request, timeout))
        return KernelResponse(status="ok", stdout="hi\n", result=3)

    def collect_outputs(self):
        return []


@pytest.fixture(autouse=True)
def clear_instances():
    FakeBackend.instances.clear()


@pytest.fixture
def daemon(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        SANDBOX_DAEMON_SECRET=SECRET,
        SANDBOX_DOCKER_BIN="docker",
        STORAGE_MAX_UPLOAD_BYTES=95 * 2**20,
        SANDBOX_KERNEL_GRACE_SECONDS=10.0,
    )
    monkeypatch.setattr(daemon_app, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "SESSIONS_ROOT", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DockerBackend", FakeBackend)
    service = store_module.SessionStore()
    monkeypatch.setattr(daemon_app, "store", service)
    return SimpleNamespace(store=service, settings=settings)


def tar_bytes() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo("notes.txt")
        info.size = 3
        archive.addfile(info, io.BytesIO(b"hi\n"))
    return buffer.getvalue()


async def create_session(client, session_id="run-1"):
    request = client.build_request(
        "POST",
        "/sessions",
        data={"session_id": session_id, "spec": json.dumps({"max_run_seconds": 1800})},
        files={"data": ("data.tar", tar_bytes())},
    )
    body = request.read()
    request.headers["X-Mokinjay-Signature"] = sign(SECRET, int(time.time()), body)
    return await client.send(request)


def job_body(job_id="job-1"):
    return json.dumps(
        {"job_id": job_id, "request": JobRequest(kind="python", timeout=5.0, code="1+2").to_payload()}
    ).encode()


async def post_job(client, job_id="job-1", body=None, session_id="run-1"):
    payload = body if body is not None else job_body(job_id)
    request = client.build_request(
        "POST",
        f"/sessions/{session_id}/jobs",
        content=payload,
        headers={"content-type": "application/json"},
    )
    request.headers["X-Mokinjay-Signature"] = sign(SECRET, int(time.time()), payload)
    return await client.send(request)


@pytest.fixture
async def client(daemon):
    async with AsyncClient(transport=ASGITransport(app=daemon_app.app), base_url="http://daemon") as http:
        yield http


@pytest.mark.asyncio
async def test_a_job_returns_the_kernel_response_payload(client):
    await create_session(client)

    response = await post_job(client)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["stdout"] == "hi\n"
    assert payload["result"] == 3


@pytest.mark.asyncio
async def test_the_same_job_id_runs_the_code_once(client):
    await create_session(client)

    first = await post_job(client)
    second = await post_job(client)

    assert first.status_code == 200
    assert first.json() == second.json()
    assert len(FakeBackend.instances[0].calls) == 1


@pytest.mark.asyncio
async def test_a_different_job_id_runs_again(client):
    await create_session(client)

    await post_job(client, job_id="job-1")
    await post_job(client, job_id="job-2")

    assert len(FakeBackend.instances[0].calls) == 2


@pytest.mark.asyncio
async def test_a_job_on_an_unknown_session_is_404(client):
    response = await post_job(client)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_a_backend_failure_returns_a_typed_error(client, monkeypatch):
    await create_session(client)

    def explode(self, _request, _timeout):
        raise SandboxError("container_error", "boom")

    monkeypatch.setattr(FakeBackend, "run", explode)
    response = await post_job(client)

    assert response.status_code == 502
    assert response.json()["kind"] == "container_error"
    assert response.json()["message"] == "boom"


@pytest.mark.asyncio
async def test_a_malformed_payload_is_422(client):
    await create_session(client)

    response = await post_job(client, body=b'{"job_id": "job-1"}')

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_the_host_patience_includes_the_kernel_grace(client):
    await create_session(client)

    await post_job(client)

    _request, timeout = FakeBackend.instances[0].calls[0]
    assert timeout == 15.0
