"""The Docker sandbox: a per-agent capability that executes code in isolation (ADR-010).

The public surface is deliberately small. `SandboxSession` is what a run holds,
`select_backend` decides where its kernel runs, and the result dataclasses are what
callers read. Everything else here is implementation of that one interface, because
the sandbox is a service several features borrow — not a knowledge-base feature.
"""

from app.services.sandbox.backends import (
    KERNEL_PATH,
    BackendFactory,
    ContainerSpec,
    IsolationBackend,
    SandboxConfig,
    SubprocessBackend,
    docker_reachable,
    kernel_failure,
    select_backend,
)
from app.services.sandbox.docker_backend import DockerBackend
from app.services.sandbox.errors import ErrorInfo, ErrorKind, SandboxError
from app.services.sandbox.protocol import (
    JobRequest,
    KernelResponse,
    classify,
    send_request,
)

__all__ = [
    "BackendFactory",
    "ContainerSpec",
    "DockerBackend",
    "ErrorInfo",
    "ErrorKind",
    "IsolationBackend",
    "JobRequest",
    "KERNEL_PATH",
    "KernelResponse",
    "SandboxConfig",
    "SandboxError",
    "SubprocessBackend",
    "classify",
    "docker_reachable",
    "kernel_failure",
    "select_backend",
    "send_request",
]
