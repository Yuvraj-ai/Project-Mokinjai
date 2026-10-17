"""The sandbox's wire protocol and its verdict on a reply.

The framing is duplicated in `kernel.py`, which cannot import this package, so the
tests that keep the two honest are the kernel's own (test_sandbox_kernel.py) and
run the real kernel. These tests cover the pieces that are pure: framing,
serialisation and classification.
"""

import json
import socket
import struct
import threading

import pytest

from app.services.sandbox.errors import ErrorKind, ErrorInfo, SandboxError
from app.services.sandbox.protocol import (
    MAX_FRAME_BYTES,
    JobRequest,
    KernelResponse,
    classify,
    encode_message,
    send_request,
)


class TestFraming:
    def test_a_message_round_trips(self):
        payload = {"kind": "python", "code": "print(1)", "timeout": 30.0}

        assert json.loads(encode_message(payload)[4:].decode()) == payload

    def test_the_header_is_a_four_byte_big_endian_length(self):
        frame = encode_message({"a": 1})
        body = json.dumps({"a": 1}).encode()

        assert struct.unpack("!I", frame[:4])[0] == len(body)
        assert frame[4:] == body

    def test_send_request_reads_one_reply_over_a_real_socket(self, tmp_path):
        socket_path = str(tmp_path / "kernel.sock")
        ready = threading.Event()

        def serve():
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(socket_path)
                server.listen(1)
                ready.set()
                connection, _ = server.accept()
                with connection:
                    connection.recv(4)
                    connection.sendall(encode_message({"status": "ok", "stdout": "hi\n"}))

        server = threading.Thread(target=serve)
        server.start()
        try:
            assert ready.wait(timeout=5), "server did not bind socket in time"
            reply = send_request(socket_path, {"kind": "python"}, timeout=5)
        finally:
            server.join(timeout=5)

        assert reply["status"] == "ok"
        assert reply["stdout"] == "hi\n"


class TestJobRequest:
    def test_the_payload_carries_every_field_the_kernel_reads(self):
        request = JobRequest(kind="tool", timeout=7.0, tool_name="add", tool_args={"a": 1})

        assert request.to_payload() == {
            "kind": "tool",
            "timeout": 7.0,
            "code": None,
            "inputs": {},
            "tool_name": "add",
            "tool_source": None,
            "tool_args": {"a": 1},
        }


class TestClassification:
    def test_a_clean_reply_has_no_error_even_with_output_on_stderr(self):
        response = KernelResponse(status="ok", stdout="42\n", stderr="a warning\n")

        assert classify(response) is None

    def test_a_raised_exception_is_a_code_error_carrying_the_traceback(self):
        response = KernelResponse(
            status="error",
            stderr="boom\n",
            error_type="ValueError",
            error_message="boom",
            traceback="Traceback (most recent call last):\nValueError: boom",
        )

        info = classify(response)

        assert info.kind == ErrorKind.CODE_ERROR.value
        assert info.message == "boom"
        assert "ValueError: boom" in info.detail

    def test_a_deadline_is_a_timeout_and_says_so(self):
        response = KernelResponse(
            status="timeout",
            error_type="DeadlineExceeded",
            error_message="Execution was killed after 30s.",
        )

        info = classify(response)

        assert info.kind == ErrorKind.TIMEOUT.value
        assert "30s" in info.message

    def test_the_kinds_are_distinct_strings(self):
        assert len({kind.value for kind in ErrorKind}) == len(ErrorKind)

    def test_sandbox_error_carries_its_info(self):
        error = SandboxError(ErrorKind.IMAGE_MISSING, "not built", "build it")

        assert error.info == ErrorInfo(ErrorKind.IMAGE_MISSING.value, "not built", "build it")
        assert "not built" in str(error)
