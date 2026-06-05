"""SSRF protection for the public API.

When the auditor is exposed on the internet, anyone can ask it to fetch a URL.
Without a guard, a caller could point it at internal/cloud-metadata addresses
(e.g. 169.254.169.254) and use the server as a proxy. This module rejects any
URL that is not a normal, public http(s) endpoint.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURLError(ValueError):
    """Raised when a URL is not safe to fetch from a public deployment."""


_BLOCKED_HOSTNAMES = {"localhost", "metadata", "metadata.google.internal"}


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def ensure_public_url(url: str) -> str:
    """Return ``url`` if it is a public http(s) address, else raise :class:`UnsafeURLError`."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURLError("Only http:// and https:// URLs can be audited.")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("URL has no host.")
    if host.lower() in _BLOCKED_HOSTNAMES:
        raise UnsafeURLError("Refusing to audit a local or metadata host.")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise UnsafeURLError(f"Could not resolve host: {host}") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked_ip(ip):
            raise UnsafeURLError("Refusing to audit a private or internal address.")
    return url
