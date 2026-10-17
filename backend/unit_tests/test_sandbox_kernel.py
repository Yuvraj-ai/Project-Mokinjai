"""The sandbox kernel, driven over its real socket.

No Docker here: the kernel is a plain process, and the subprocess backend runs this
same file. These tests launch it with `sys.executable` — the venv under pytest — and
speak the wire protocol to it, so the framing in `kernel.py` and the framing in
`protocol.py` are checked against each other rather than against a mock.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.services.sandbox.protocol import send_request

KERNEL_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "sandbox" / "kernel.py"


class KernelDriver:
    """Launches the kernel and drives it, the way a backend does."""

    def __init__(self, socket_path: str, root: Path):
        self.socket_path = socket_path
        self.root = root

    def job(self, **request):
        request.setdefault("kind", "python")
        request.setdefault("timeout", 10.0)
        return send_request(self.socket_path, request, timeout=request["timeout"] + 10)

    def run(self, code, **request):
        return self.job(code=code, **request)

    @property
    def outputs(self) -> dict[str, bytes]:
        directory = self.root / "output"
        found = {}
        for dirpath, _dirs, names in os.walk(directory):
            for name in names:
                full = Path(dirpath) / name
                found[str(full.relative_to(directory))] = full.read_bytes()
        return found


@pytest.fixture
def kernel(tmp_path):
    for name in ("data", "work", "output"):
        (tmp_path / name).mkdir()
    socket_path = str(tmp_path / "kernel.sock")
    process = subprocess.Popen(
        [
            sys.executable,
            str(KERNEL_PATH),
            "--socket", socket_path,
            "--data-dir", str(tmp_path / "data"),
            "--work-dir", str(tmp_path / "work"),
            "--output-dir", str(tmp_path / "output"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    for _ in range(300):
        if os.path.exists(socket_path):
            break
        time.sleep(0.01)
    else:
        process.kill()
        raise AssertionError(f"the kernel never created its socket: {process.stderr.read()!r}")

    yield KernelDriver(socket_path, tmp_path)

    process.terminate()
    process.wait(timeout=5)


class TestStatefulness:
    def test_a_variable_bound_by_one_job_is_readable_by_the_next(self, kernel):
        kernel.run("answer = 40 + 2")

        response = kernel.run("print(answer)")

        assert response["status"] == "ok"
        assert response["stdout"] == "42\n"

    def test_imports_and_function_definitions_persist(self, kernel):
        kernel.run("import math\ndef area(r):\n    return math.pi * r * r")

        response = kernel.run("print(round(area(1), 3))")

        assert response["stdout"] == "3.142\n"

    def test_a_scratch_file_written_by_one_job_is_visible_to_the_next(self, kernel):
        kernel.run("open('/tmp/scratch.txt', 'w').write('kept')")

        response = kernel.run("print(open('/tmp/scratch.txt').read())")

        assert response["stdout"] == "kept\n"


class TestOutputCapture:
    def test_stdout_and_stderr_are_separated(self, kernel):
        response = kernel.run("import sys\nprint('out')\nsys.stderr.write('err\\n')")

        assert response["stdout"] == "out\n"
        assert response["stderr"] == "err\n"

    def test_stderr_alone_does_not_make_a_job_a_failure(self, kernel):
        response = kernel.run("import sys\nsys.stderr.write('just a warning\\n')")

        assert response["status"] == "ok"


class TestFailures:
    def test_a_raised_exception_is_reported_and_the_kernel_survives(self, kernel):
        response = kernel.run("survived = 'yes'\nraise ValueError('boom')")

        assert response["status"] == "error"
        assert response["error_type"] == "ValueError"
        assert response["error_message"] == "boom"
        assert "ValueError: boom" in response["traceback"]

        after = kernel.run("print(survived)")
        assert after["status"] == "ok"
        assert after["stdout"] == "yes\n"

    def test_a_syntax_error_is_reported_as_a_failure(self, kernel):
        response = kernel.run("def broken(:\n    pass")

        assert response["status"] == "error"
        assert response["error_type"] == "SyntaxError"

    def test_a_job_that_overruns_its_limit_is_killed_and_the_kernel_survives(self, kernel):
        response = kernel.run("kept = 'before'\nwhile True:\n    pass", timeout=0.5)

        assert response["status"] == "timeout"
        assert response["error_type"] == "DeadlineExceeded"
        assert "0.5s" in response["error_message"]

        after = kernel.run("print(kept)")
        assert after["status"] == "ok"
        assert after["stdout"] == "before\n"


    def test_timeout_cannot_be_caught_by_guest_broad_exception_handler(self, kernel):
        code = (
            "try:\n"
            "    while True:\n"
            "        pass\n"
            "except Exception:\n"
            "    pass\n"
        )
        response = kernel.run(code, timeout=0.5)

        assert response["status"] == "timeout"
        assert response["error_type"] == "DeadlineExceeded"


class TestFiles:
    def test_files_written_outside_the_output_directory_are_not_collected(self, kernel):
        kernel.run("open('/tmp/report.csv', 'w').write('a,b\\n1,2\\n')")

        assert kernel.outputs == {}


class TestOutputDirectoryIsPerCall:
    def test_a_file_from_the_previous_job_is_cleared_before_the_next(self, kernel, tmp_path):
        kernel.run(f"open('{tmp_path / 'output' / 'first.txt'}', 'w').write('one')")
        assert kernel.outputs == {"first.txt": b"one"}

        kernel.run("pass")

        assert kernel.outputs == {}, "output must be per call, not accumulated across the run"


class TestInputs:
    def test_a_per_call_input_is_written_into_the_work_directory(self, kernel, tmp_path):
        import base64

        response = kernel.run(
            "print(open('" + str(tmp_path / "work" / "inputs" / "note.txt") + "').read())",
            inputs={"note.txt": base64.b64encode(b"hello").decode()},
        )

        assert response["stdout"] == "hello\n"

    def test_the_previous_call_s_inputs_are_gone(self, kernel, tmp_path):
        import base64

        kernel.run("pass", inputs={"old.txt": base64.b64encode(b"old").decode()})
        kernel.run("pass")

        assert not (tmp_path / "work" / "inputs" / "old.txt").exists()

    def test_an_input_name_that_escapes_the_directory_is_refused(self, kernel):
        import base64

        response = kernel.run(
            "pass", inputs={"../escape.txt": base64.b64encode(b"no").decode()}
        )

        assert response["status"] == "error"
        assert "escapes" in response["error_message"]


def test_the_kernel_imports_nothing_from_the_application():
    """It runs in the container, where `app` does not exist, and for the venv fallback.

    A stray `from app.config import get_settings` would work under the subprocess
    backend and fail inside the container, which is the worst way to discover it.
    """
    source = KERNEL_PATH.read_text()

    assert "from app" not in source
    assert "import app" not in source
    assert "app.services" not in source
