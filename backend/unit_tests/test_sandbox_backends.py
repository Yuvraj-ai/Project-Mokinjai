"""The backend interface, its configuration, and the subprocess fallback.

The subprocess backend is the dev fallback: the same kernel in the repository's venv,
with a time limit and nothing else. It exists so the interface is exercisable on a
machine where /var/run/docker.sock cannot be reached, which is this one.
"""

import os
from pathlib import Path
import time

import pytest

from app.services.sandbox.backends import (
    ContainerSpec,
    SandboxConfig,
    SubprocessBackend,
    docker_reachable,
    kernel_failure,
)
from app.services.sandbox.errors import ErrorKind, SandboxError
from app.services.sandbox.protocol import JobRequest


def spec(tmp_path, **overrides):
    values = dict(
        name="mokinjay-sandbox-test",
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
        labels={"mokinjay.run": "test"},
    )
    values.update(overrides)
    return ContainerSpec(**values)


class TestContainerSpec:
    def test_every_host_path_is_derived_from_the_host_root(self, tmp_path):
        built = spec(tmp_path)

        assert built.host_ipc_dir == os.path.join(str(tmp_path), "ipc")
        assert built.host_data_dir == os.path.join(str(tmp_path), "data")
        assert built.host_work_dir == os.path.join(str(tmp_path), "work")
        assert built.host_output_dir == os.path.join(str(tmp_path), "output")
        assert built.host_socket_path == os.path.join(str(tmp_path), "ipc", "kernel.sock")


class TestSandboxConfig:
    def test_it_defaults_to_the_limits_adr_010_records(self):
        config = SandboxConfig()

        assert config.memory == "256m"
        assert config.cpus == "0.5"
        assert config.network == "none"
        assert config.read_only is True
        assert config.user == "1000:1000"
        assert config.timeout_seconds == 30.0

    def test_it_reads_settings(self):
        from app.config import get_settings

        settings = get_settings()

        assert SandboxConfig.from_settings(settings).image == settings.SANDBOX_IMAGE

    def test_it_builds_a_spec_named_after_the_run(self, tmp_path):
        built = SandboxConfig().container_spec(run_id="abc123", host_root=str(tmp_path))

        assert built.name == "mokinjay-sandbox-abc123"
        assert built.labels == {"mokinjay.run": "abc123"}
        assert built.host_root == str(tmp_path)


class TestDockerReachable:
    def test_a_missing_binary_is_not_reachable(self):
        assert docker_reachable("/nonexistent/docker-binary") is False


class TestKernelFailure:
    def test_an_oom_kill_is_a_resource_limit(self):
        error = kernel_failure("the socket dropped", oom_killed=True)

        assert error.info.kind == ErrorKind.RESOURCE_LIMIT.value

    def test_any_other_death_is_a_container_error(self):
        error = kernel_failure("the socket dropped", oom_killed=False)

        assert error.info.kind == ErrorKind.CONTAINER_ERROR.value
        assert error.info.detail == "the socket dropped"


class TestSubprocessBackend:
    def test_the_backend_satisfies_the_protocol(self, tmp_path):
        from app.services.sandbox.backends import IsolationBackend

        assert isinstance(SubprocessBackend(spec(tmp_path)), IsolationBackend)

    def test_it_starts_runs_and_stops(self, tmp_path):
        backend = SubprocessBackend(spec(tmp_path))
        backend.start()
        try:
            assert backend.is_alive()

            response = backend.run(JobRequest(kind="python", code="print('up')", timeout=5), timeout=10)

            assert response.status == "ok"
            assert response.stdout == "up\n"
        finally:
            backend.stop()

        assert not backend.is_alive()

    def test_it_holds_state_across_jobs(self, tmp_path):
        backend = SubprocessBackend(spec(tmp_path))
        backend.start()
        try:
            backend.run(JobRequest(kind="python", code="carried = 'over'", timeout=5), timeout=10)

            response = backend.run(JobRequest(kind="python", code="print(carried)", timeout=5), timeout=10)

            assert response.stdout == "over\n"
        finally:
            backend.stop()

    def test_it_collects_the_output_directory(self, tmp_path):
        backend = SubprocessBackend(spec(tmp_path))
        backend.start()
        try:
            backend.run(
                JobRequest(
                    kind="python",
                    code=f"open({str(tmp_path / 'output' / 'made.txt')!r}, 'w').write('data')",
                    timeout=5,
                ),
                timeout=10,
            )

            assert backend.collect_outputs() == [("made.txt", b"data")]
        finally:
            backend.stop()

    def test_an_unresponsive_kernel_is_torn_down_and_reported_as_a_timeout(self, tmp_path):
        # The kernel's SIGALRM handles a normal overrun. This drives the backstop: a
        # socket timeout far shorter than the job the kernel was asked for.
        backend = SubprocessBackend(spec(tmp_path))
        backend.start()
        try:
            with pytest.raises(SandboxError) as caught:
                backend.run(
                    JobRequest(kind="python", code="import time\nwhile True: time.sleep(0.05)", timeout=30),
                    timeout=0.5,
                )

            assert caught.value.info.kind == ErrorKind.TIMEOUT.value
            assert not backend.is_alive(), "the backstop must tear the sandbox down, not leave it running"
        finally:
            backend.stop()

    def test_running_a_job_after_stop_is_a_container_error(self, tmp_path):
        backend = SubprocessBackend(spec(tmp_path))
        backend.start()
        backend.stop()

        with pytest.raises(SandboxError) as caught:
            backend.run(JobRequest(kind="python", code="pass", timeout=5), timeout=10)

        assert caught.value.info.kind == ErrorKind.CONTAINER_ERROR.value


class TestSelectBackend:
    def test_auto_chooses_docker_when_the_probe_succeeds(self, monkeypatch):
        from app.services.sandbox import backends

        monkeypatch.setattr(backends, "docker_reachable", lambda *a, **k: True)

        factory = backends.select_backend(SandboxConfig(backend="auto"))

        assert factory(spec(Path("/tmp"))).name == "docker"

    def test_auto_falls_back_when_the_probe_fails(self, monkeypatch):
        from app.services.sandbox import backends

        monkeypatch.setattr(backends, "docker_reachable", lambda *a, **k: False)

        factory = backends.select_backend(SandboxConfig(backend="auto"))

        assert factory(spec(Path("/tmp"))).name == "subprocess"

    def test_docker_is_required_when_it_is_named(self, monkeypatch):
        from app.services.sandbox import backends

        monkeypatch.setattr(backends, "docker_reachable", lambda *a, **k: False)

        with pytest.raises(SandboxError) as caught:
            backends.select_backend(SandboxConfig(backend="docker"))

        assert caught.value.info.kind == ErrorKind.BACKEND_UNAVAILABLE.value
        assert "docker.sock" in caught.value.info.detail

    def test_subprocess_never_probes_docker(self, monkeypatch):
        from app.services.sandbox import backends

        def explode(*args, **kwargs):
            raise AssertionError("the subprocess backend must not probe Docker")

        monkeypatch.setattr(backends, "docker_reachable", explode)

        factory = backends.select_backend(SandboxConfig(backend="subprocess"))

        assert factory(spec(Path("/tmp"))).name == "subprocess"

    def test_an_unknown_backend_is_refused(self):
        from app.services.sandbox import backends

        with pytest.raises(SandboxError) as caught:
            backends.select_backend(SandboxConfig(backend="sausages"))

        assert caught.value.info.kind == ErrorKind.BACKEND_UNAVAILABLE.value

