"""The Docker sandbox: a per-agent capability that executes code in isolation (ADR-010).

The public surface is deliberately small. `SandboxSession` is what a run holds,
`select_backend` decides where its kernel runs, and the result dataclasses are what
callers read. Everything else here is implementation of that one interface, because
the sandbox is a service several features borrow — not a knowledge-base feature.
"""

from app.services.sandbox.backends import (
    KERNEL_PATH,
    ContainerSpec,
    IsolationBackend,
    SandboxConfig,
    SubprocessBackend,
    docker_reachable,
    kernel_failure,
)
from app.services.sandbox.errors import ErrorInfo, ErrorKind, SandboxError
from app.services.sandbox.protocol import (
    JobRequest,
    KernelResponse,
    classify,
    send_request,
)

__all__ = [
    "KERNEL_PATH",
    "ContainerSpec",
    "ErrorInfo",
    "ErrorKind",
    "IsolationBackend",
    "JobRequest",
    "KernelResponse",
    "SandboxConfig",
    "SandboxError",
    "SubprocessBackend",
    "classify",
    "docker_reachable",
    "kernel_failure",
    "send_request",
]
