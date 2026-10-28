"""Relative paths that may be shown, skipped, or refused."""

from __future__ import annotations

from enum import Enum

_GENERATED_ROOTS = frozenset({"vendor", "generated", "var", "node_modules"})
_GENERATED_PREFIXES = (
    "pub/static/",
    "pub/media/",
    "dev/tests/integration/tmp/",
    "dev/tests/integration/sandbox/",
)
_SENSITIVE_NAMES = frozenset(
    {
        ".env",
        "auth.json",
        ".netrc",
        ".npmrc",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "credentials.json",
    }
)
_SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


class PathClass(Enum):
    VISIBLE = "visible"
    GENERATED = "generated"
    SENSITIVE = "sensitive"


def normalize_relative(value: str) -> str | None:
    """Return a repo-relative path, or None when it could leave the work tree."""
    if not value or value.startswith(("/", "\\")) or "\\" in value or "\x00" in value:
        return None
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return "/".join(parts)


def classify_relative(value: str) -> PathClass | None:
    relative = normalize_relative(value)
    if relative is None:
        return None
    name = relative.rsplit("/", 1)[-1]
    if name == ".env" or name.startswith(".env.") or name in _SENSITIVE_NAMES:
        return PathClass.SENSITIVE
    if name.endswith(_SENSITIVE_SUFFIXES) or relative == "app/etc/env.php":
        return PathClass.SENSITIVE
    root = relative.split("/", 1)[0]
    if root in _GENERATED_ROOTS or relative.startswith(_GENERATED_PREFIXES):
        return PathClass.GENERATED
    return PathClass.VISIBLE
