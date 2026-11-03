"""SSRF posture for data-source dials (D6).

Cloud metadata endpoints are refused before any socket is opened. Private
ranges stay allowed — self-hosted databases are the legitimate use of this
feature — and the residual risk (an editor probing arbitrary hosts:ports over
the DB wire protocol only) is accepted in the spec.
"""

import ipaddress
import socket
from urllib.parse import urlsplit

# Exact endpoints, blocked as literal hostnames and again after resolution
# (metadata.google.internal resolves to 169.254.169.254 on GCP).
_BLOCKED_HOSTS = {
    "169.254.169.254",
    "fd00:ec2::254",
    "metadata.google.internal",
    "100.100.100.200",
}

# Resolution itself must never touch a blocked host, so the literal check
# happens before any DNS lookup.
_BLOCKED_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in ("169.254.0.0/16",)  # link-local, where cloud metadata lives
)


class BlockedHostError(Exception):
    """The URI points at a cloud metadata endpoint."""


def extract_host(uri: str) -> str:
    host = urlsplit(uri).hostname or ""
    return host.strip("[]").lower()


def assert_dial_allowed(uri: str) -> None:
    """Raise BlockedHostError if the URI targets a metadata endpoint."""
    host = extract_host(uri)
    netloc = urlsplit(uri).netloc.lower()
    if not host and not netloc:
        raise BlockedHostError("the connection URI has no host")

    # A bare IPv6 literal (no brackets) confuses urlsplit's hostname parsing,
    # so the netloc is scanned as well — both spellings are refused.
    for candidate in {host, netloc}:
        for blocked in _BLOCKED_HOSTS:
            if blocked in candidate:
                raise BlockedHostError(f"connections to {blocked} are not allowed")

    if host:
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError:
            # Unresolvable: the dial itself will fail with a sanitized error.
            return
        for info in infos:
            address = ipaddress.ip_address(info[4][0])
            if address.compressed in _BLOCKED_HOSTS:
                raise BlockedHostError(
                    f"connections to {address.compressed} are not allowed"
                )
            if any(address in network for network in _BLOCKED_NETWORKS):
                raise BlockedHostError(
                    f"connections to {address.compressed} are not allowed"
                )
