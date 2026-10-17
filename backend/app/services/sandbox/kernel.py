"""The sandbox kernel: runs jobs statefully, inside the sandbox.

Stands alone on purpose. It executes in the container, which has the standard library
and the parsing libraries but *not* this application, so it imports nothing from
`app.*`; the subprocess fallback runs this same file with the repository's venv as its
interpreter, so the two backends differ in isolation only, never in behaviour.

Statefulness lives here, in one namespace dict reused by every job: a variable bound by
one call is still bound by the next. That is what ADR-010 means by "stateful within the
run", and it is why the container is started once per run rather than once per call —
a fresh `python job.py` per call would start a fresh interpreter and lose the namespace.

The per-job time limit is a SIGALRM, which raises inside the running code in the main
thread instead of killing the process, so the namespace and the files written before
the deadline survive a timeout. A job that defers signals — a long C-level routine that
never returns to the interpreter — can overshoot; the host's socket timeout is the
backstop, and it tears the whole session down when it fires.

The framing here (a 4-byte big-endian length, then UTF-8 JSON) must match
`app/services/sandbox/protocol.py`. It is duplicated rather than imported because this
file has to run where that package does not exist.
"""

import argparse
import base64
import io
import json
import os
import signal
import socket
import struct
import traceback
from contextlib import redirect_stderr, redirect_stdout

HEADER = struct.Struct("!I")
MAX_FRAME_BYTES = 16 * 1024 * 1024


class DeadlineExceeded(Exception):
    """Raised inside the running job when its time limit expires."""


def _on_alarm(signum, frame):
    raise DeadlineExceeded("the job exceeded its time limit")


class SandboxContext:
    """The `ctx` bound into a user-defined tool's execution namespace.

    Offline by construction, and that is the resolution of a contradiction in the
    recorded design. The tool design said a tool body runs with a `ctx` giving it
    database, HTTP and knowledge-base access; ADR-010 runs this container with
    `--network none`, and there is no database and no object-storage credential inside
    it. So `ctx` exposes exactly what the container can reach: the read-only
    knowledge-base files under `data_dir`, and the writable output and work directories.

    A tool that needs a database, an HTTP call or object storage calls a host-side tool
    for it, where the credentials already live (ADR-020). The capability moves from
    sandboxed code to trusted host code rather than being faked here, and there is
    deliberately no `ctx.database`, `ctx.http` or `ctx.knowledge_base`: a surface that
    does not exist cannot be reached by mistake.
    """

    def __init__(self, data_dir, output_dir, work_dir):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.work_dir = work_dir

    # -- the mounted knowledge base, read-only ------------------------------ #

    def list_inputs(self):
        """Names of the files mounted under the data directory, relative and sorted."""
        found = []
        for root, _directories, names in os.walk(self.data_dir):
            for name in names:
                full = os.path.join(root, name)
                found.append(os.path.relpath(full, self.data_dir))
        return sorted(found)

    def input_path(self, name):
        """The absolute path of a mounted file, for handing straight to pandas."""
        return self._inside(self.data_dir, name)

    def read_input(self, name):
        with open(self.input_path(name), "rb") as handle:
            return handle.read()

    # -- writable paths ----------------------------------------------------- #

    def write_output(self, name, data):
        """Write into the output directory, which the caller collects. Returns the path."""
        if isinstance(data, str):
            data = data.encode("utf-8")
        path = self._inside(self.output_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def work_file(self, name):
        """A writable scratch path that survives between calls within the run."""
        return self._inside(self.work_dir, name)

    def log(self, message):
        print(message)

    @staticmethod
    def _inside(root, name):
        """Resolve `name` under `root`, refusing anything that climbs out of it."""
        if not name or os.path.isabs(name):
            raise ValueError(f"{name!r} must be a relative path inside the sandbox")
        root = os.path.realpath(root)
        path = os.path.realpath(os.path.join(root, name))
        if path != root and not path.startswith(root + os.sep):
            raise ValueError(f"{name!r} escapes the sandbox directory")
        return path


class Kernel:
    """Serves jobs over a Unix socket, holding one namespace for the run."""

    def __init__(self, data_dir, work_dir, output_dir, socket_path):
        self.data_dir = data_dir
        self.work_dir = work_dir
        self.output_dir = output_dir
        self.socket_path = socket_path
        self.namespace = {"__name__": "__sandbox__"}

    # -- lifecycle ---------------------------------------------------------- #

    def serve_forever(self):
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.socket_path)
        server.listen(4)
        try:
            while True:
                connection, _ = server.accept()
                with connection:
                    try:
                        reply = self.run(_read_frame(connection))
                    except Exception as exc:
                        # The kernel's own failure, not the job's: a malformed frame or a
                        # protocol mismatch must be reported rather than crash the run.
                        reply = {
                            "status": "error",
                            "error_type": type(exc).__name__,
                            "error_message": str(exc),
                            "traceback": traceback.format_exc(),
                        }
                    connection.sendall(_frame(json.dumps(reply)))
        finally:
            server.close()
            if os.path.exists(self.socket_path):
                os.unlink(self.socket_path)

    # -- one job ------------------------------------------------------------ #

    def run(self, payload):
        stdout, stderr = io.StringIO(), io.StringIO()
        timeout = float(payload.get("timeout") or 30.0)

        self._reset_directories()
        try:
            self._write_inputs(payload.get("inputs") or {})
        except Exception as exc:
            return self._failure("error", stdout, stderr, exc)

        previous_handler = signal.signal(signal.SIGALRM, _on_alarm)
        signal.setitimer(signal.ITIMER_REAL, timeout)
        try:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = self._dispatch(payload)
        except DeadlineExceeded:
            return {
                "status": "timeout",
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "error_type": "DeadlineExceeded",
                "error_message": f"Execution was killed after {timeout:g}s.",
                "traceback": traceback.format_exc(),
            }
        except BaseException as exc:
            # The job's failure, not the kernel's. SystemExit and KeyboardInterrupt
            # are caught too: a job calling sys.exit() must not take the run down.
            return self._failure("error", stdout, stderr, exc)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)

        return {
            "status": "ok",
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "result": result,
        }

    def _dispatch(self, payload):
        kind = payload.get("kind")
        if kind == "python":
            return self._run_python(payload)
        if kind == "tool":
            return self._run_tool(payload)
        raise ValueError(f"unknown job kind {kind!r}")

    def _run_python(self, payload):
        code = compile(payload.get("code") or "", "<sandbox>", "exec")
        exec(code, self.namespace)
        return None

    def _run_tool(self, payload):
        """Run one user-defined tool, in a fresh namespace, with `ctx` injected.

        A fresh namespace per call, unlike `_run_python`: a tool call must not depend on
        what another tool call happened to leave behind. What a tool *writes* through
        `ctx.write_output` or `ctx.work_file` does persist, and is the statefulness that
        matters for a tool.
        """
        name = payload.get("tool_name") or ""
        source = payload.get("tool_source") or ""
        arguments = payload.get("tool_args") or {}

        namespace = {"__name__": f"__tool_{name}__"}
        context = SandboxContext(self.data_dir, self.output_dir, self.work_dir)
        namespace["ctx"] = context
        exec(compile(source, f"<tool:{name}>", "exec"), namespace)

        function = namespace.get(name)
        if not callable(function):
            raise RuntimeError(
                f"The source for tool '{name}' does not define a function of that name."
            )

        result = function(**arguments)
        # The result has to cross the wire, so it has to be JSON. A DataFrame or a
        # custom object is refused here, with the type named, rather than truncating the
        # reply at the framing layer where the reason would be invisible.
        try:
            json.dumps(result)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"Tool '{name}' returned {type(result).__name__}, which cannot be sent back "
                f"to the caller: tool results must be JSON-serialisable ({exc})."
            ) from exc
        return result

    @staticmethod
    def _failure(status, stdout, stderr, exc):
        return {
            "status": status,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
        }

    # -- files -------------------------------------------------------------- #

    def _reset_directories(self):
        """Empty the output and per-call input directories.

        Output is emptied per job so that the files the host collects after a call are
        that call's files and not the run's. Inputs are emptied so that a call cannot
        read the previous call's payload.
        """
        _empty_directory(self.output_dir)
        _empty_directory(os.path.join(self.work_dir, "inputs"))

    def _write_inputs(self, inputs):
        target = os.path.join(self.work_dir, "inputs")
        os.makedirs(target, exist_ok=True)
        for name, encoded in inputs.items():
            if not name or os.path.isabs(name) or ".." in name.split("/"):
                raise ValueError(f"{name!r} escapes the sandbox; must be a relative path inside the sandbox")
            path = os.path.join(target, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(base64.b64decode(encoded))


def _empty_directory(path):
    os.makedirs(path, exist_ok=True)
    for root, directories, names in os.walk(path, topdown=False):
        for name in names:
            os.unlink(os.path.join(root, name))
        for name in directories:
            os.rmdir(os.path.join(root, name))


def _frame(payload):
    body = payload.encode("utf-8")
    return HEADER.pack(len(body)) + body


def _read_exactly(connection, count):
    chunks = bytearray()
    while len(chunks) < count:
        chunk = connection.recv(count - len(chunks))
        if not chunk:
            raise ConnectionError("the host closed the connection mid-frame")
        chunks.extend(chunk)
    return bytes(chunks)


def _read_frame(connection):
    (length,) = HEADER.unpack(_read_exactly(connection, HEADER.size))
    if length > MAX_FRAME_BYTES:
        raise ValueError(f"a frame of {length} bytes exceeds the {MAX_FRAME_BYTES}-byte cap")
    return json.loads(_read_exactly(connection, length).decode("utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mokinjay sandbox kernel")
    parser.add_argument("--socket", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    Kernel(
        data_dir=args.data_dir,
        work_dir=args.work_dir,
        output_dir=args.output_dir,
        socket_path=args.socket,
    ).serve_forever()


if __name__ == "__main__":
    main()
