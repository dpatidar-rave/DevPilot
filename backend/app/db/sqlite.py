"""SQLite file helpers. Other database URLs never reach this module."""

from pathlib import Path


def sqlite_path(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("Only a local SQLite file is supported.")
    return Path(database_url[len(prefix) :])


def restrict_file(path: Path) -> None:
    if path.exists():
        path.chmod(0o600)
