"""Shared fixtures. Environment defaults are applied before the app is imported."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_DEFAULT_DB = _BACKEND / ".pytest_tmp" / "default.sqlite"
_DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)

os.environ.setdefault("DEVPILOT_DATABASE_URL", f"sqlite:///{_DEFAULT_DB}")
os.environ.setdefault("DEVPILOT_HOST", "127.0.0.1")
os.environ.setdefault("DEVPILOT_OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def upgrade_database(url: str) -> None:
    """Apply migrations to a local SQLite file."""
    os.environ["DEVPILOT_DATABASE_URL"] = url
    from alembic import command
    from alembic.config import Config

    config = Config(str(_BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")


@pytest.fixture()
def database_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Migrated SQLite file that is removed with the test."""
    url = f"sqlite:///{tmp_path / 'devpilot.sqlite'}"
    monkeypatch.setenv("DEVPILOT_DATABASE_URL", url)
    upgrade_database(url)
    return url
