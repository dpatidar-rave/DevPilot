"""Local-only configuration checks."""

from __future__ import annotations

import ipaddress
import socket
from typing import Callable, List, Sequence
from urllib.parse import urlparse

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

LOCAL_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
)

OLLAMA_RETRY_INSTRUCTIONS = (
    "Start Ollama on this machine with `ollama serve`.",
    "Confirm it is listening on the local address (default http://127.0.0.1:11434).",
    "Retry the check from DevPilot. This app will not switch to a hosted model.",
)

DATABASE_RETRY_INSTRUCTIONS = (
    "From the backend directory, run `alembic upgrade head`.",
    "Restart the API with `python -m app`, then retry.",
)


class LocalOnlyError(ValueError):
    """Raised when configuration would leave the local machine."""


def assert_loopback_host(host: str) -> str:
    """Return a normalized loopback host or reject the value."""
    normalized = host.strip()
    if normalized not in LOOPBACK_HOSTS:
        raise LocalOnlyError(
            f"Refusing to bind {host!r}. DevPilot only serves localhost "
            "(127.0.0.1, localhost, or ::1)."
        )
    return normalized


def assert_loopback_http_url(
    url: str,
    resolve: Callable[[str], Sequence[str]] | None = None,
) -> str:
    """Allow only an http URL that resolves exclusively to loopback.

    The returned URL uses the loopback address, so a later DNS change cannot
    redirect the request.
    """
    parsed = urlparse(url.strip())
    hostname = parsed.hostname
    if parsed.scheme != "http" or not hostname:
        raise LocalOnlyError(
            "Ollama must be a local http endpoint. Hosted model APIs are not allowed."
        )
    if parsed.username is not None or parsed.password is not None:
        raise LocalOnlyError("Ollama URLs must not include credentials.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise LocalOnlyError("Ollama URL must not include a path, query, or fragment.")
    port = parsed.port or 80
    host = _canonical_loopback_host(hostname, resolve or _resolve_hostname)
    return f"http://{host}:{port}"


def _canonical_loopback_host(hostname: str, resolve: Callable[[str], Sequence[str]]) -> str:
    literal = _literal_ip(hostname)
    if literal is not None:
        if not literal.is_loopback:
            raise LocalOnlyError(
                "Ollama endpoint must use a loopback address. Remote inference endpoints are rejected."
            )
        return _format_ip(literal)
    try:
        resolved = list(resolve(hostname))
    except LocalOnlyError:
        raise
    except OSError as exc:
        raise LocalOnlyError(
            "Ollama endpoint did not resolve to a loopback address."
        ) from exc
    addresses: List[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for item in resolved:
        parsed = _literal_ip(item.split("%", 1)[0])
        if parsed is None or not parsed.is_loopback:
            raise LocalOnlyError(
                "Ollama endpoint must resolve only to loopback addresses. "
                "Remote inference endpoints are rejected."
            )
        addresses.append(parsed)
    if not addresses:
        raise LocalOnlyError("Ollama endpoint did not resolve to a loopback address.")
    for address in addresses:
        if address == ipaddress.ip_address("127.0.0.1"):
            return "127.0.0.1"
    return _format_ip(addresses[0])


def _literal_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _format_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    if isinstance(address, ipaddress.IPv6Address):
        return f"[{address.compressed}]"
    return str(address)


def _resolve_hostname(hostname: str) -> List[str]:
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise LocalOnlyError(
            "Ollama endpoint did not resolve to a loopback address."
        ) from exc
    return [str(info[4][0]) for info in infos if info[4]]


def assert_local_sqlite(url: str) -> str:
    """Allow a local SQLite file or an in-memory database used by tests."""
    if not url.startswith("sqlite:///"):
        raise LocalOnlyError("Only a local SQLite database is allowed.")
    location = url[len("sqlite:///") :]
    if location == ":memory:":
        return url
    if "://" in location or location.startswith("\\\\"):
        raise LocalOnlyError("SQLite URL must point at a local file.")
    return url
