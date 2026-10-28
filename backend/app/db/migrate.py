"""Apply the Alembic migration to the configured SQLite file."""

import sqlite3
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.config import BACKEND_DIR
from app.db.sqlite import restrict_file, sqlite_path


def init_database(database_url: str) -> None:
    path = sqlite_path(database_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    backend = str(BACKEND_DIR)
    if backend not in sys.path:
        sys.path.insert(0, backend)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    head = ScriptDirectory.from_config(config).get_current_head()
    if path.is_file() and read_schema_version(path) != head:
        backup_database(path)
    command.upgrade(config, "head")
    restrict_file(path)


def read_schema_version(path: Path) -> str | None:
    """Return the stored Alembic revision, or an empty string when it cannot be read."""
    if not path.is_file() or path.stat().st_size == 0:
        return None
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return ""
    try:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.Error:
        return ""
    finally:
        connection.close()
    if row is None or not isinstance(row[0], str):
        return ""
    return row[0]


def backup_database(path: Path) -> Path:
    """Copy the database beside itself before a schema change. The copy is mode 0600."""
    destination = path.with_name(path.name + ".bak")
    source = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    restrict_file(destination)
    return destination
