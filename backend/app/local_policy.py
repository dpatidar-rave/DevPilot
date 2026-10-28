"""Rules that keep DevPilot on the local machine."""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

BIND_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
OLLAMA_KEEP_ALIVE = "10m"
DEFAULT_MODEL = "qwen2.5-coder:7b"
LARGE_MODEL_PARAMETER_THRESHOLD = 20

_CLOUD_HOST_MARKERS = (
    "openai",
    "anthropic",
    "googleapis",
    "azure",
    "amazonaws",
    "openrouter",
    "groq.com",
    "mistral.ai",
    "cohere.ai",
    "huggingface.co",
    "replicate.com",
    "together.ai",
    "fireworks.ai",
    "ollama.com",
    "generativelanguage",
)

_CLOUD_MODEL_PATTERN = re.compile(
    r"(?i)(?:^|[^a-z0-9])(?:"
    r"gpt-|chatgpt|claude|gemini|text-davinci|text-embedding-|dall-e|"
    r"openai|anthropic|openrouter|bedrock|vertex-ai|azure-openai"
    r")|(?:^|[^a-z0-9])o[13](?:$|[^a-z0-9])"
)
_MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_PARAMETER_PATTERN = re.compile(r"(?i)(?:^|[^0-9])(\d+)b(?:$|[^a-z0-9])")


def validate_bind_host(value: str) -> str:
    """Accept only loopback names that the server is allowed to bind."""
    host = value.strip().lower()
    if host not in BIND_HOSTS:
        shown = host[:80]
        raise ValueError(
            "DevPilot only binds to a loopback address "
            f"(127.0.0.1, localhost, or ::1). {shown!r} is not allowed."
        )
    return host


def validate_frontend_origin(value: str) -> str:
    """Restrict the browser origin to this machine."""
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise ValueError("DEVPILOT_FRONTEND_ORIGIN must be an http(s) loopback origin.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("DEVPILOT_FRONTEND_ORIGIN cannot include credentials or a query.")
    if parsed.path not in {"", "/"}:
        raise ValueError("DEVPILOT_FRONTEND_ORIGIN cannot include a path.")
    host = validate_bind_host(parsed.hostname)
    port = parsed.port
    location = f"[{host}]" if ":" in host else host
    if port is None:
        return f"{parsed.scheme}://{location}"
    return f"{parsed.scheme}://{location}:{port}"


def loopback_origin_aliases(origin: str) -> list[str]:
    """Allow the configured origin and the matching localhost / 127.0.0.1 spelling."""
    parsed = urlparse(origin)
    if parsed.hostname is None or parsed.port is None:
        return [origin]
    aliases = [origin]
    for host in ("127.0.0.1", "localhost"):
        candidate = f"{parsed.scheme}://{host}:{parsed.port}"
        if candidate not in aliases:
            aliases.append(candidate)
    return aliases


def canonical_sqlite_url(url: str, *, repo_root: str) -> str:
    """Resolve a SQLite file URL and reject every other database."""
    if not url.startswith("sqlite:///") or any(token in url for token in ("?", "#", "@")):
        raise ValueError(
            "DEVPILOT_DATABASE_URL must be a local SQLite file. Remote databases are not supported."
        )
    raw = url[len("sqlite:///") :]
    if raw in {"", ":memory:"}:
        raise ValueError("DevPilot requires a SQLite file, not an in-memory database.")
    from pathlib import Path

    path = Path(raw)
    if not path.is_absolute():
        path = Path(repo_root) / path
    resolved = path.resolve()
    return "sqlite:///" + resolved.as_posix()


def canonical_directory(value: str, *, repo_root: str) -> str:
    from pathlib import Path

    path = Path(value)
    if not path.is_absolute():
        path = Path(repo_root) / path
    return str(path.resolve())


def validate_ollama_endpoint(value: str) -> str:
    """Accept an Ollama origin only when every resolved address is loopback."""
    candidate = value.strip()
    if len(candidate) > 200:
        raise ValueError("Ollama endpoint is too long.")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Ollama endpoint must use http or https.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Ollama endpoint cannot include credentials, a query, or a fragment.")
    if parsed.path not in {"", "/"}:
        raise ValueError("Ollama endpoint must be an origin without a path.")
    host = parsed.hostname
    if host is None or parsed.port is None:
        raise ValueError("Ollama endpoint must include a loopback host and an explicit port.")
    lowered = host.lower().rstrip(".")
    if any(marker in lowered for marker in _CLOUD_HOST_MARKERS):
        raise ValueError(
            "Remote inference endpoints are not allowed. "
            "Point DevPilot at the Ollama server on this machine."
        )
    try:
        infos = socket.getaddrinfo(lowered, parsed.port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(
            "Ollama endpoint must resolve to a loopback address. "
            "DevPilot will not send review data to a remote inference service."
        ) from exc
    addresses = {item[4][0] for item in infos}
    if not addresses or not all(_address_is_loopback(address) for address in addresses):
        raise ValueError(
            "Ollama endpoint must resolve only to a loopback address. "
            "DevPilot rejected a non-loopback address."
        )
    location = f"[{lowered}]" if ":" in lowered else lowered
    return f"{parsed.scheme.lower()}://{location}:{parsed.port}"


def validate_model_name(name: str, *, large_model_confirmed: bool) -> str:
    """Reject hosted model names. Large local models require an explicit confirmation."""
    candidate = name.strip()
    if _MODEL_NAME_PATTERN.fullmatch(candidate) is None:
        raise ValueError(
            "Model name must be a local Ollama tag made of letters, numbers, and . _ : / -."
        )
    if _CLOUD_MODEL_PATTERN.search(candidate):
        raise ValueError(
            "Hosted model names are not allowed. "
            f"The local default is {DEFAULT_MODEL}."
        )
    sizes = [int(match) for match in _PARAMETER_PATTERN.findall(candidate)]
    largest = max(sizes, default=0)
    if largest >= LARGE_MODEL_PARAMETER_THRESHOLD and not large_model_confirmed:
        raise ValueError(
            f"{candidate} is {largest}B parameters. On a 16 GB Mac the default is "
            f"{DEFAULT_MODEL}. Models at {LARGE_MODEL_PARAMETER_THRESHOLD}B or larger are an "
            "optional experiment and require large_model_confirmed=true after you accept the "
            "extra memory use. DevPilot will not switch to this model silently."
        )
    return candidate


def _address_is_loopback(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if address.is_loopback:
        return True
    mapped = getattr(address, "ipv4_mapped", None)
    return mapped is not None and mapped.is_loopback
