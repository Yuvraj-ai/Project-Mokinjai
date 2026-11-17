"""Request signing for the sandbox daemon: the layer we own.

The InstaBox private-port proxy already requires its own bearer token. This signature
is a second, independently rotatable check, computed over the exact bytes the daemon
received so a re-serialised body cannot drift between client and server.
"""

import hashlib
import hmac
import time

MAX_SKEW_SECONDS = 300
_HEADER_PREFIX = "v1="


def _digest(secret: str, timestamp: int, body: bytes) -> str:
    message = f"{timestamp}.".encode() + body
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def sign(secret: str, timestamp: int, body: bytes) -> str:
    """The header value: `t=<unix seconds>,v1=<hex hmac>`."""
    return f"t={timestamp},{_HEADER_PREFIX}{_digest(secret, timestamp, body)}"


def verify(
    secret: str,
    header: str | None,
    body: bytes,
    now: int | None = None,
) -> str | None:
    """`None` means accepted; otherwise a short reason, never the secret."""
    if not header:
        return "missing signature"
    parts = dict(part.split("=", 1) for part in header.split(",") if "=" in part)
    try:
        timestamp = int(parts["t"])
    except (KeyError, ValueError):
        return "malformed signature"
    signature = parts.get("v1")
    if not signature:
        return "malformed signature"
    if abs((now if now is not None else int(time.time())) - timestamp) > MAX_SKEW_SECONDS:
        return "stale timestamp"
    if not hmac.compare_digest(signature, _digest(secret, timestamp, body)):
        return "bad signature"
    return None
