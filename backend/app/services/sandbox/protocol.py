"""The host-to-kernel wire protocol, and the classifier for a kernel's reply.

The kernel (`kernel.py`) runs *inside* the sandbox and imports nothing from this
application — the container has the standard library and the parsing libraries but
not the `app` package, and the subprocess fallback runs the same file. So the framing
is duplicated there under a comment that says so, and the tests that keep the two
honest run the real kernel rather than a mock.

Transport is a Unix domain socket on a directory bind-mounted into the container. A
socket rather than TCP because `--network none` is the sandbox's isolation guarantee
(ADR-010); a Unix socket is a filesystem object and is unaffected by a network
namespace.
"""

import json
import socket
import struct
from dataclasses import dataclass
from typing import Any

from app.services.sandbox.errors import ErrorInfo, ErrorKind

_HEADER = struct.Struct("!I")

# The frame cap bounds the control channel. It is not the bound on generated files,
# which the output tmpfs caps instead: files travel by the filesystem, not by frame.
MAX_FRAME_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class JobRequest:
    """One job for the kernel.

    `inputs` values are base64 of the raw bytes: the payload is JSON, and per-call
    inputs are small by design — a run's large knowledge-base files are bind-mounted
    into the sandbox once instead of being sent per call.
    """

    kind: str
    timeout: float
    code: str | None = None
    inputs: dict[str, str] | None = None
    tool_name: str | None = None
    tool_source: str | None = None
    tool_args: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "timeout": self.timeout,
            "code": self.code,
            "inputs": self.inputs or {},
            "tool_name": self.tool_name,
            "tool_source": self.tool_source,
            "tool_args": self.tool_args or {},
        }


@dataclass(frozen=True)
class KernelResponse:
    """A kernel's raw reply, before it is classified."""

    status: str                                   # "ok" | "error" | "timeout"
    stdout: str = ""
    stderr: str = ""
    result: Any = None
    error_type: str | None = None
    error_message: str | None = None
    traceback: str | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "KernelResponse":
        return cls(
            status=payload["status"],
            stdout=payload.get("stdout", ""),
            stderr=payload.get("stderr", ""),
            result=payload.get("result"),
            error_type=payload.get("error_type"),
            error_message=payload.get("error_message"),
            traceback=payload.get("traceback"),
        )


def encode_message(payload: dict[str, Any]) -> bytes:
    """One frame: a 4-byte big-endian length, then the UTF-8 JSON body."""
    body = json.dumps(payload).encode("utf-8")
    return _HEADER.pack(len(body)) + body


def _read_exactly(connection, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        chunk = connection.recv(count - len(chunks))
        if not chunk:
            raise ConnectionError("the sandbox kernel closed the connection mid-frame")
        chunks.extend(chunk)
    return bytes(chunks)


def read_message(sock) -> dict[str, Any]:
    """Read exactly one frame. Raises `ConnectionError` if the peer goes away."""
    (length,) = _HEADER.unpack(_read_exactly(sock, _HEADER.size))
    if length > MAX_FRAME_BYTES:
        raise ConnectionError(
            f"a frame of {length} bytes exceeds the {MAX_FRAME_BYTES}-byte cap"
        )
    return json.loads(_read_exactly(sock, length).decode("utf-8"))


def send_request(socket_path: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """Send one request and read one reply, over a fresh connection.

    A fresh connection per job rather than a pooled one: the kernel serves one
    connection at a time, so a pooled socket would have to be re-established after any
    failure anyway, and the connect cost over a Unix socket is negligible.
    """
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(socket_path)
        sock.sendall(encode_message(payload))
        return read_message(sock)


def classify(response: KernelResponse) -> ErrorInfo | None:
    """The sandbox's verdict. `None` means the code ran and returned."""
    if response.status == "ok":
        return None
    if response.status == "timeout":
        return ErrorInfo(
            kind=ErrorKind.TIMEOUT.value,
            message=response.error_message or "Execution timed out and was killed.",
            detail=response.traceback,
        )
    return ErrorInfo(
        kind=ErrorKind.CODE_ERROR.value,
        message=response.error_message
        or f"{response.error_type or 'Exception'} raised by the executed code.",
        detail=response.traceback,
    )
