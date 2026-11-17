"""Generated files leave the daemon as one tar, never as a JSON frame."""

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
from app.services.sandbox.protocol import KernelResponse

SECRET = "test-daemon-secret"


class FakeBackend:
    outputs: list[tuple[str, bytes]] = []

    def __init__(self, spec):
        self.spec = spec
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def is_alive(self):
        return self.started

    def run(self, request, timeout):
        return KernelResponse(status="ok")

    def collect_outputs(self):
        return list(FakeBackend.outputs)


@pytest.fixture(autouse=True)
def clear_outputs():
    FakeBackend.outputs[:] = []


@pytest.fixture
def daemon(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        SANDBOX_DAEMON_SECRET=SECRET,
        SANDBOX_DOCKER_BIN="docker",
        STORAGE_MAX_UPLOAD_BYTES=95 * 2**20,
    )
    monkeypatch.setattr(daemon_app, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "SESSIONS_ROOT", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DockerBackend", FakeBackend)
    service = store_module.SessionStore()
    monkeypatch.setattr(daemon_app, "store", service)
    return SimpleNamespace(store=service)


def tar_bytes() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo("notes.txt")
        info.size = 3
        archive.addfile(info, io.BytesIO(b"hi\n"))
    return buffer.getvalue()


async def create_session(client):
    request = client.build_request(
        "POST",
        "/sessions",
        data={"session_id": "run-1", "spec": json.dumps({"max_run_seconds": 1800})},
        files={"data": ("data.tar", tar_bytes())},
    )
    body = request.read()
    request.headers["X-Mokinjay-Signature"] = sign(SECRET, int(time.time()), body)
    return await client.send(request)


async def get_outputs(client, session_id="run-1"):
    request = client.build_request("GET", f"/sessions/{session_id}/outputs")
    request.headers["X-Mokinjay-Signature"] = sign(SECRET, int(time.time()), b"")
    return await client.send(request)


@pytest.fixture
async def client(daemon):
    async with AsyncClient(transport=ASGITransport(app=daemon_app.app), base_url="http://daemon") as http:
        yield http


def unpack(payload: bytes) -> dict[str, bytes]:
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:*") as archive:
        return {
            member.name: archive.extractfile(member).read()
            for member in archive.getmembers()
            if member.isfile()
        }


@pytest.mark.asyncio
async def test_outputs_are_returned_as_a_tar(client):
    await create_session(client)
    FakeBackend.outputs = [("chart.png", b"png")]

    response = await get_outputs(client)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-tar"
    assert unpack(response.content) == {"chart.png": b"png"}


@pytest.mark.asyncio
async def test_outputs_of_an_unknown_session_is_404(client):
    response = await get_outputs(client, session_id="missing")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_outputs_are_empty_when_nothing_was_generated(client):
    await create_session(client)

    response = await get_outputs(client)

    assert response.status_code == 200
    assert unpack(response.content) == {}
