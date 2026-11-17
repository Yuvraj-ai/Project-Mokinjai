"""The daemon's session lifecycle: create, inspect, delete.

The tests swap `DockerBackend` for a fake. No Docker and no VM is required; the only
thing under test here is the registry, the tar boundary, and the routes above them.
"""

import io
import json
import os
import tarfile
import time
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.services.sandbox.daemon import app as daemon_app
from app.services.sandbox.daemon import store as store_module
from app.services.sandbox.daemon.auth import sign
from app.services.sandbox.errors import SandboxError

SECRET = "test-daemon-secret"


class FakeBackend:
    instances: list["FakeBackend"] = []

    def __init__(self, spec):
        self.spec = spec
        self.started = False
        self.stopped = False
        FakeBackend.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def is_alive(self):
        return self.started and not self.stopped


@pytest.fixture(autouse=True)
def clear_instances():
    FakeBackend.instances.clear()


@pytest.fixture
def daemon(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        SANDBOX_DAEMON_SECRET=SECRET,
        SANDBOX_DOCKER_BIN="docker",
        STORAGE_MAX_UPLOAD_BYTES=95 * 2**20,
        SANDBOX_IMAGE="mokinjay-sandbox:1",
        SANDBOX_MEMORY="256m",
        SANDBOX_CPUS="0.5",
        SANDBOX_MAX_RUN_SECONDS=1800,
    )
    monkeypatch.setattr(daemon_app, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "get_settings", lambda: settings)
    monkeypatch.setattr(store_module, "SESSIONS_ROOT", tmp_path / "sessions")
    monkeypatch.setattr(store_module, "DockerBackend", FakeBackend)
    service = store_module.SessionStore()
    monkeypatch.setattr(daemon_app, "store", service)
    return SimpleNamespace(store=service, settings=settings, root=tmp_path / "sessions")


def tar_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def spec_json(**overrides) -> str:
    values = {
        "image": "mokinjay-sandbox:1",
        "memory": "256m",
        "cpus": "0.5",
        "user": "1000:1000",
        "network": "none",
        "read_only": True,
        "output_tmpfs_mb": 64,
        "work_tmpfs_mb": 64,
        "max_run_seconds": 1800,
    }
    values.update(overrides)
    return json.dumps(values)


async def post_session(client, session_id="run-1", spec=None, data=None):
    request = client.build_request(
        "POST",
        "/sessions",
        data={"session_id": session_id, "spec": spec or spec_json()},
        files={"data": ("data.tar", data if data is not None else tar_bytes({"notes.txt": b"hello"}))},
    )
    body = request.read()
    request.headers["X-Mokinjay-Signature"] = sign(SECRET, int(time.time()), body)
    return await client.send(request)


async def get_signed(client, path):
    request = client.build_request("GET", path)
    request.headers["X-Mokinjay-Signature"] = sign(SECRET, int(time.time()), b"")
    return await client.send(request)


async def delete_signed(client, path):
    request = client.build_request("DELETE", path)
    request.headers["X-Mokinjay-Signature"] = sign(SECRET, int(time.time()), b"")
    return await client.send(request)


@pytest.fixture
async def client(daemon):
    async with AsyncClient(transport=ASGITransport(app=daemon_app.app), base_url="http://daemon") as http:
        yield http


@pytest.mark.asyncio
async def test_creating_a_session_starts_a_backend(client, daemon):
    response = await post_session(client)

    assert response.status_code == 201
    assert len(FakeBackend.instances) == 1
    assert FakeBackend.instances[0].started is True
    assert (daemon.root / "run-1" / "data" / "notes.txt").read_bytes() == b"hello"


@pytest.mark.asyncio
async def test_a_session_upload_rejects_path_traversal(client, daemon):
    payload = tar_bytes({"../../etc/passwd": b"nope"})

    response = await post_session(client, data=payload)

    assert response.status_code == 400
    assert not list(daemon.root.parent.rglob("passwd"))
    assert FakeBackend.instances == []


@pytest.mark.asyncio
async def test_a_bad_session_id_is_rejected(client):
    response = await post_session(client, session_id="../../etc")

    assert response.status_code == 400
    assert FakeBackend.instances == []


@pytest.mark.asyncio
async def test_creating_the_same_session_twice_is_idempotent(client):
    first = await post_session(client)
    second = await post_session(client)

    assert first.status_code == 201
    assert second.status_code == 200
    assert len(FakeBackend.instances) == 1


@pytest.mark.asyncio
async def test_a_retried_create_replaces_a_stale_root(client, daemon):
    stale = daemon.root / "run-1" / "data"
    stale.mkdir(parents=True)
    (stale / "junk.txt").write_bytes(b"junk")

    response = await post_session(client)

    assert response.status_code == 201
    assert not (stale / "junk.txt").exists()
    assert (stale / "notes.txt").read_bytes() == b"hello"


@pytest.mark.asyncio
async def test_creating_removes_a_container_left_by_a_dead_daemon(client, daemon, monkeypatch):
    commands = []
    monkeypatch.setattr(
        store_module.subprocess,
        "run",
        lambda command, **_kwargs: commands.append(command) or SimpleNamespace(returncode=1),
    )

    response = await post_session(client)

    assert response.status_code == 201
    assert ["docker", "rm", "-f", "run-1"] in commands


@pytest.mark.asyncio
async def test_old_session_roots_are_pruned(client, daemon):
    old = daemon.root / "leaked"
    old.mkdir(parents=True)
    stamp = time.time() - (1800 + 3600 + 60)
    os.utime(old, (stamp, stamp))
    fresh = daemon.root / "recent"
    fresh.mkdir(parents=True)

    await post_session(client)

    assert not old.exists()
    assert fresh.exists()


@pytest.mark.asyncio
async def test_inspecting_an_unknown_session_is_404(client):
    response = await get_signed(client, "/sessions/missing")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_inspecting_a_session_reports_alive(client):
    await post_session(client)

    response = await get_signed(client, "/sessions/run-1")

    assert response.status_code == 200
    assert response.json() == {"session_id": "run-1", "alive": True}


@pytest.mark.asyncio
async def test_deleting_a_session_stops_the_backend_and_removes_the_directory(client, daemon):
    await post_session(client)

    response = await delete_signed(client, "/sessions/run-1")

    assert response.status_code == 204
    assert FakeBackend.instances[0].stopped is True
    assert not (daemon.root / "run-1").exists()


@pytest.mark.asyncio
async def test_deleting_twice_is_not_an_error(client):
    await post_session(client)

    first = await delete_signed(client, "/sessions/run-1")
    second = await delete_signed(client, "/sessions/run-1")

    assert first.status_code == 204
    assert second.status_code == 204


@pytest.mark.asyncio
async def test_session_routes_require_a_valid_signature(client):
    response = await client.get("/sessions/run-1")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_a_third_session_is_refused_with_503(client):
    first = await post_session(client, session_id="run-1")
    second = await post_session(client, session_id="run-2")
    third = await post_session(client, session_id="run-3")

    assert (first.status_code, second.status_code) == (201, 201)
    assert third.status_code == 503
    assert len(FakeBackend.instances) == 2


def test_the_ipc_directory_is_handed_to_the_container_user(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(store_module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        store_module.os, "chown", lambda path, uid, gid: calls.append((str(path), uid, gid))
    )
    ipc = tmp_path / "ipc"
    ipc.mkdir()

    store_module._own_for_container(ipc, "1000:1000")

    assert calls == [(str(ipc), 1000, 1000)]


@pytest.mark.asyncio
async def test_a_failed_start_releases_the_admission_slot(client, monkeypatch):
    original = FakeBackend.start

    def explode(self):
        raise SandboxError("container_error", "boom")

    monkeypatch.setattr(FakeBackend, "start", explode)
    failed = await post_session(client, session_id="run-1")
    monkeypatch.setattr(FakeBackend, "start", original)

    recovered = await post_session(client, session_id="run-2")

    assert failed.status_code == 502
    assert recovered.status_code == 201
