"""execute_python, against the real kernel through the subprocess backend.

The subprocess backend is used deliberately: these assertions are about the contract of
`execute_python`, not about Docker, and they must run on a machine where
/var/run/docker.sock cannot be reached. On that backend the host paths *are* the
sandbox paths, which is what lets a test name the output directory directly.
"""

import threading
import time

import pytest

from app.services.sandbox.backends import SandboxConfig
from app.services.sandbox.errors import ErrorKind
from app.services.sandbox.session import SandboxSession


@pytest.fixture
def session(tmp_path):
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "one.txt").write_text("first")
    (tmp_path / "documents" / "two.txt").write_text("second")

    # No backend is injected: the session derives the container spec and the subprocess
    # backend consumes it, so `session.output_dir` and the backend's directories are one
    # and the same tree. That is what lets these tests name the output, data and work
    # directories directly.
    built = SandboxSession(
        config=SandboxConfig(backend="subprocess", timeout_seconds=10),
        data_dir=str(tmp_path / "documents"),
        run_id="execute-tests",
    )
    yield built
    built.close()


class TestResults:
    def test_a_clean_job_returns_its_stdout_and_no_error(self, session):
        result = session.execute_python("print('hello')")

        assert result.stdout == "hello\n"
        assert result.stderr == ""
        assert result.error is None

    def test_state_carries_between_calls(self, session):
        session.execute_python("total = 3")

        result = session.execute_python("print(total * 2)")

        assert result.stdout == "6\n"

    def test_stderr_without_a_failure_is_not_an_error(self, session):
        result = session.execute_python("import sys\nsys.stderr.write('warning\\n')")

        assert result.stderr == "warning\n"
        assert result.error is None

    def test_a_raised_exception_is_a_code_error_with_a_traceback(self, session):
        result = session.execute_python("raise ValueError('nope')")

        assert result.error.kind == ErrorKind.CODE_ERROR.value
        assert result.error.message == "nope"
        assert "ValueError: nope" in result.error.detail


class TestGeneratedFiles:
    def test_a_file_written_to_the_output_directory_comes_back_with_its_contents(self, session):
        result = session.execute_python(
            f"open({str(session.output_dir / 'report.csv')!r}, 'w').write('a,b\\n1,2\\n')"
        )

        assert [(f.name, f.size, f.data) for f in result.generated_files] == [
            ("report.csv", 8, b"a,b\n1,2\n")
        ]

    def test_a_job_that_writes_nothing_returns_no_files(self, session):
        result = session.execute_python("print('nothing produced')")

        assert result.generated_files == []

    def test_generated_files_are_per_call(self, session):
        session.execute_python(
            f"open({str(session.output_dir / 'first.txt')!r}, 'w').write('one')"
        )

        second = session.execute_python("pass")

        assert second.generated_files == [], "output must be per call, not accumulated across the run"


class TestTheKnowledgeBaseMount:
    def test_the_run_s_documents_are_readable_by_the_code(self, session):
        path = session.output_dir.parent / "data" / "one.txt"

        result = session.execute_python(f"print(open({str(path)!r}).read(), end='')")

        assert result.stdout == "first"

    def test_the_documents_are_all_present(self, session):
        path = session.output_dir.parent / "data"

        result = session.execute_python(f"import os\nprint(sorted(os.listdir({str(path)!r})))")

        assert result.stdout == "['one.txt', 'two.txt']\n"


class TestInputFiles:
    def test_a_per_call_file_is_written_into_the_sandbox(self, session):
        work = session.output_dir.parent / "work" / "inputs"

        result = session.execute_python(
            f"print(open({str(work / 'note.txt')!r}).read(), end='')",
            files={"note.txt": b"from the caller"},
        )

        assert result.stdout == "from the caller"

    def test_an_input_name_that_escapes_is_a_programmer_error(self, session):
        with pytest.raises(ValueError):
            session.execute_python("pass", files={"../escape.txt": b"no"})

    def test_an_input_that_is_not_bytes_is_refused(self, session):
        with pytest.raises(TypeError):
            session.execute_python("pass", files={"note.txt": "a string, not bytes"})


class TestTimeouts:
    def test_a_job_that_overruns_reports_a_timeout(self, session):
        result = session.execute_python("while True:\n    pass", timeout=0.5)

        assert result.error.kind == ErrorKind.TIMEOUT.value
        assert "0.5s" in result.error.message

    def test_the_session_survives_a_timeout(self, session):
        session.execute_python("kept = 'yes'")

        result = session.execute_python("while True:\n    pass", timeout=0.5)
        assert result.error.kind == ErrorKind.TIMEOUT.value

        after = session.execute_python("print(kept)")
        assert after.stdout == "yes\n"


class TestConcurrency:
    def test_two_concurrent_calls_start_one_container_and_do_not_overlap(self, session, monkeypatch):
        """The lock is what stops two tool calls creating two containers.

        The kernel is a single namespace, so two jobs inside it at once would interleave
        assignments. They are serialised instead, and the guarantee offered is ordering
        rather than parallelism.
        """
        overlap = []
        running = []
        original = session._dispatch

        def slow_dispatch(request):
            running.append(1)
            if len(running) > 1:
                overlap.append(1)
            time.sleep(0.15)
            try:
                return original(request)
            finally:
                running.pop()

        monkeypatch.setattr(session, "_dispatch", slow_dispatch)

        threads = [
            threading.Thread(target=session.execute_python, args=(f"job_{index} = {index}",))
            for index in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert overlap == [], "two jobs must not be inside the kernel at the same time"
        assert session.started is True


class TestAfterClose:
    def test_a_closed_session_reports_a_container_error_rather_than_raising(self, session):
        session.close()

        result = session.execute_python("print('too late')")

        assert result.error.kind == ErrorKind.CONTAINER_ERROR.value
        assert "closed" in result.error.message
        assert result.stdout == ""
