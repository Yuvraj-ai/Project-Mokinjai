"""The Docker backend, against a real daemon.

Marked `docker`, so these skip unless the socket is reachable and the image is built.
Run them through the group:

    newgrp docker -c "cd backend && MOKINJAY_SANDBOX_DOCKER=1 ./venv/bin/python -m pytest unit_tests/test_sandbox_docker_backend.py -q -m docker"
"""

import subprocess
import uuid
from pathlib import Path

import pytest

from app.services.sandbox.backends import SandboxConfig
from app.services.sandbox.docker_backend import DockerBackend, sweep
from app.services.sandbox.errors import ErrorKind, SandboxError
from app.services.sandbox.protocol import JobRequest

pytestmark = pytest.mark.docker


def run(*args, timeout=60):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


@pytest.fixture
def backend(tmp_path):
    config = SandboxConfig()
    spec = config.container_spec(run_id=uuid.uuid4().hex[:8], host_root=str(tmp_path))
    (tmp_path / "data").mkdir()

    built = DockerBackend(spec)
    built.start()
    try:
        yield built
    finally:
        built.stop()


class TestLifecycle:
    def test_it_starts_and_stops_a_container(self, backend):
        assert backend.is_alive()

        backend.stop()

        assert not backend.is_alive()

    def test_stop_is_idempotent(self, backend):
        backend.stop()
        backend.stop()

        assert not backend.is_alive()

    def test_it_leaves_no_container_behind(self, tmp_path):
        config = SandboxConfig()
        spec = config.container_spec(run_id=uuid.uuid4().hex[:8], host_root=str(tmp_path))
        (tmp_path / "data").mkdir()
        built = DockerBackend(spec)
        built.start()
        assert run("docker", "ps", "-q", "--filter", f"name={spec.name}").stdout.strip()

        built.stop()

        assert run("docker", "ps", "-aq", "--filter", f"name={spec.name}").stdout.strip() == ""

    def test_a_job_runs_in_the_container(self, backend):
        response = backend.run(JobRequest(kind="python", code="print('in-container')", timeout=10), timeout=20)

        assert response.status == "ok"
        assert response.stdout == "in-container\n"

    def test_the_kernel_holds_state_across_jobs_in_the_container(self, backend):
        backend.run(JobRequest(kind="python", code="carried = 'across'", timeout=10), timeout=20)

        response = backend.run(JobRequest(kind="python", code="print(carried)", timeout=10), timeout=20)

        assert response.stdout == "across\n"

    def test_the_libraries_are_available_to_a_job(self, backend):
        response = backend.run(
            JobRequest(kind="python", code="import pandas; print(pandas.__name__)", timeout=30),
            timeout=45,
        )

        assert response.stdout.strip() == "pandas"

    def test_the_data_directory_is_mounted_read_only(self, backend, tmp_path):
        (tmp_path / "data" / "note.txt").write_text("hello")
        response = backend.run(
            JobRequest(
                kind="python",
                code=(
                    "print(open('/app/data/note.txt').read(), end='')\n"
                    "try:\n"
                    "    open('/app/data/note.txt', 'w').write('no')\n"
                    "except OSError:\n"
                    "    print('read-only')\n"
                ),
                timeout=10,
            ),
            timeout=20,
        )

        assert response.status == "ok"

    def test_generated_files_come_back_to_the_host(self, backend, tmp_path):
        backend.run(
            JobRequest(
                kind="python",
                code="open('/app/output/report.csv', 'w').write('a,b\\n1,2\\n')",
                timeout=10,
            ),
            timeout=20,
        )

        assert backend.collect_outputs() == [("report.csv", b"a,b\n1,2\n")]

    def test_a_job_that_overruns_returns_a_timeout_and_the_container_survives(self, backend):
        response = backend.run(
            JobRequest(kind="python", code="kept = 'before'\nwhile True:\n    pass", timeout=2),
            timeout=20,
        )

        assert response.status == "timeout"
        assert backend.is_alive(), "a timeout kills the job, not the run's sandbox"

        after = backend.run(JobRequest(kind="python", code="print(kept)", timeout=10), timeout=20)
        assert after.stdout == "before\n"

    def test_a_job_that_exceeds_the_memory_limit_is_not_a_code_error(self, backend):
        try:
            response = backend.run(
                JobRequest(
                    kind="python",
                    code="blob = bytearray(600 * 1024 * 1024)",
                    timeout=30,
                ),
                timeout=45,
            )
            assert response.status in {"error", "timeout"}
        except SandboxError as caught:
            assert caught.info.kind == ErrorKind.RESOURCE_LIMIT.value


class TestImageGate:
    def test_a_missing_image_is_reported_before_docker_run_is_attempted(self, tmp_path):
        from app.services.sandbox.errors import ErrorKind, SandboxError

        config = SandboxConfig(image="mokinjay-does-not-exist:0")
        spec = config.container_spec(run_id="missing", host_root=str(tmp_path))
        (tmp_path / "data").mkdir()
        built = DockerBackend(spec)

        with pytest.raises(SandboxError) as caught:
            built.start()

        assert caught.value.info.kind == ErrorKind.IMAGE_MISSING.value
        assert "docker build -f docker/Dockerfile.sandbox" in caught.value.info.message


class TestSweep:
    def test_it_removes_a_stale_labelled_container_and_spares_others(self):
        name = f"mokinjay-sandbox-sweep-{uuid.uuid4().hex[:8]}"
        run("docker", "run", "-d", "--rm", "--name", name,
            "--label", "mokinjay.sandbox=1", "mokinjay-sandbox:1", "sleep", "300")
        try:
            assert sweep("docker", 99999) == 0
            assert sweep("docker", 0) >= 1
            assert run("docker", "ps", "-aq", "--filter", f"name={name}").stdout.strip() == ""
        finally:
            run("docker", "rm", "-f", name)

    def test_it_never_touches_an_unlabelled_container(self):
        name = f"not-a-sandbox-{uuid.uuid4().hex[:8]}"
        run("docker", "run", "-d", "--rm", "--name", name, "mokinjay-sandbox:1", "sleep", "300")
        try:
            sweep("docker", 0)

            assert run("docker", "ps", "-q", "--filter", f"name={name}").stdout.strip() != ""
        finally:
            run("docker", "rm", "-f", name)


class TestExecutePythonInTheContainer:
    def test_the_data_mount_is_read_only_and_output_is_collected(self, tmp_path):
        from app.services.sandbox.session import SandboxSession

        (tmp_path / "documents").mkdir()
        (tmp_path / "documents" / "note.txt").write_text("mounted")
        config = SandboxConfig()

        session = SandboxSession(config=config, data_dir=str(tmp_path / "documents"))
        try:
            result = session.execute_python(
                "print(open('/app/data/note.txt').read(), end='')\n"
                "try:\n"
                "    open('/app/data/note.txt', 'w').write('no')\n"
                "except OSError:\n"
                "    print('|read-only')\n"
                "open('/app/output/report.csv', 'w').write('a,b\\n1,2\\n')\n",
            )
        finally:
            session.close()

        assert result.error is None, result.error
        assert result.stdout == "mounted|read-only\n"
        assert [(f.name, f.data) for f in result.generated_files] == [
            ("report.csv", b"a,b\n1,2\n")
        ]

