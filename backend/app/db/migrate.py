"""Apply the Alembic migration to the configured SQLite file."""

import sys

from alembic import command
from alembic.config import Config

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
    command.upgrade(config, "head")
    restrict_file(path)
