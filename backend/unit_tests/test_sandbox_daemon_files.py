"""Chunked staging for a tar larger than the InstaBox proxy's 32 MiB request cap."""

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

SECRET = "test-daemon-secret"


class FakeBackend:
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
        raise AssertionError("these tests do not execute code")

    def collect_outputs(self):
        return []


def tar_bytes(members: dict[str, bytes] | None = None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, content in (members or {}).items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def clear_instances():
    FakeBackend.instances = []


@pytest.fixture
def daemon(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        SANDBOX_DAEMON_SECRET=SECRET,
        SANDBOX_DOCKER_BIN="docker",
        STORAGE_MAX_UPLOAD_BYTES=95 * 2**20,
        SANDBOX_MAX_RUN_SECONDS=1800,
    )
    monkeypatch.setattr(daemon_app, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "SESSIONS_ROOT", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DockerBackend", FakeBackend)
    service = store_module.SessionStore()
    monkeypatch.setattr(daemon_app, "store", service)
    return SimpleNamespace(store=service, settings=settings, root=tmp_path / "sessions")


def signed(client, method, path, *, content=b""):
    request = client.build_request(method, path, content=content)
    request.headers["X-Mokinjay-Signature"] = sign(SECRET, int(time.time()), content)
    return request


async def create_session(client):
    payload = tar_bytes()
    request = client.build_request(
        "POST",
        "/sessions",
        data={"session_id": "run-1", "spec": json.dumps({"max_run_seconds": 1800})},
        files={"data": ("data.tar", payload)},
    )
    body = request.read()
    request.headers["X-Mokinjay-Signature"] = sign(SECRET, int(time.time()), body)
    return await client.send(request)


@pytest.fixture
async def client(daemon):
    async with AsyncClient(transport=ASGITransport(app=daemon_app.app), base_url="http://daemon") as http:
        yield http


@pytest.mark.asyncio
async def test_two_chunks_are_assembled_and_extracted(client, daemon):
    await create_session(client)
    payload = tar_bytes({"big.bin": b"x" * 5000})

    first = await client.send(signed(client, "POST", "/sessions/run-1/files?offset=0", content=payload[:3000]))
    second = await client.send(signed(client, "POST", "/sessions/run-1/files?offset=3000", content=payload[3000:]))
    final = await client.send(signed(client, "POST", "/sessions/run-1/files/finalize"))

    assert (first.status_code, second.status_code, final.status_code) == (204, 204, 204)
    assert (daemon.root / "run-1" / "data" / "big.bin").read_bytes() == b"x" * 5000


@pytest.mark.asyncio
async def test_an_offset_gap_is_rejected(client):
    await create_session(client)

    response = await client.send(signed(client, "POST", "/sessions/run-1/files?offset=100", content=b"abc"))

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_a_part_for_an_unknown_session_is_404(client):
    response = await client.send(signed(client, "POST", "/sessions/missing/files?offset=0", content=b"abc"))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_finalize_without_parts_is_rejected(client):
    await create_session(client)

    response = await client.send(signed(client, "POST", "/sessions/run-1/files/finalize"))

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_a_part_above_the_limit_is_413(client, daemon, monkeypatch):
    await create_session(client)
    monkeypatch.setattr(daemon_app, "_spool_limit", lambda: 4)

    response = await client.send(signed(client, "POST", "/sessions/run-1/files?offset=0", content=b"abcde"))

    assert response.status_code == 413
