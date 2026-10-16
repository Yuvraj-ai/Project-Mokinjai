"""The session: one per run, no container until code needs one, closed by the run.

No Docker here. The fake backend is what makes the lifecycle assertions meaningful —
that start happens on first use and not before, that calling it twice does not start
twice, that close is final — and it is possible because `IsolationBackend` is a
Protocol rather than an ABC.
"""

import pytest

from app.services.sandbox import session as session_module
from app.services.sandbox.backends import SandboxConfig
from app.services.sandbox.errors import SandboxError
from app.services.sandbox.session import SandboxSession


class FakeBackend:
    """A backend that records what the session asked of it, and nothing else."""

    name = "fake"

    def __init__(self):
        self.started = 0
        self.stopped = 0
        self.alive = False

    def start(self):
        self.started += 1
        self.alive = True

    def stop(self):
        self.stopped += 1
        self.alive = False

    def is_alive(self):
        return self.alive

    def run(self, request, timeout):
        raise AssertionError("this task's tests never execute code")

    def collect_outputs(self):
        return []


@pytest.fixture
def config():
    return SandboxConfig(backend="subprocess")


@pytest.fixture
def fake_backend(monkeypatch):
    """A stand-in for the isolation backend, patched in where the session reads it.

    The session derives the one `ContainerSpec` for the run and passes it to the factory
    `select_backend` returns, so substituting the factory is how a test supplies a
    backend without giving the run a second, disagreeing spec.
    """
    backend = FakeBackend()
    monkeypatch.setattr(
        session_module, "select_backend", lambda config: lambda spec: backend
    )
    return backend


class TestLazyStart:
    def test_constructing_a_session_starts_nothing(self, config, fake_backend):
        session = SandboxSession(config=config)

        assert session.started is False
        assert fake_backend.started == 0

    def test_a_session_that_is_never_used_never_starts_a_container(self, config, fake_backend):
        SandboxSession(config=config).close()

        assert fake_backend.started == 0

    def test_start_is_idempotent(self, config, fake_backend):
        session = SandboxSession(config=config)

        session.start()
        session.start()

        assert fake_backend.started == 1
        assert session.started is True

    def test_it_chooses_a_real_backend_when_nothing_is_substituted(self):
        # No fake here: SANDBOX_BACKEND is "subprocess", so this starts the fallback for
        # real. It is also what proves the session and the backend agree on one spec —
        # the session derives it, the backend consumes it.
        session = SandboxSession(config=SandboxConfig(backend="subprocess"))

        session.start()
        try:
            assert session.started is True
        finally:
            session.close()


class TestTeardown:
    def test_close_is_idempotent_and_stops_once(self, config, fake_backend):
        session = SandboxSession(config=config)
        session.start()

        session.close()
        session.close()

        assert fake_backend.stopped == 1
        assert session.started is False

    def test_close_on_a_session_that_never_started_is_safe(self, config, fake_backend):
        SandboxSession(config=config).close()

        assert fake_backend.stopped == 0

    def test_the_context_manager_closes_the_sandbox(self, config, fake_backend):
        with SandboxSession(config=config) as session:
            session.start()

        assert fake_backend.stopped == 1

    def test_a_closed_session_refuses_to_start_again(self, config, fake_backend):
        """`close()` is final. Restarting would silently give a run a second container."""
        session = SandboxSession(config=config)
        session.start()
        session.close()

        with pytest.raises(SandboxError):
            session.start()

        assert fake_backend.started == 1
        assert fake_backend.stopped == 1
