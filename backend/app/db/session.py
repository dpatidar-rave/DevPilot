"""SQLite engine and session factory."""

import sqlite3

from sqlalchemy import Engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.db.sqlite import restrict_file, sqlite_path


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(
    dbapi_connection: sqlite3.Connection,
    connection_record: object,
) -> None:
    del connection_record
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(database_url: str) -> Engine:
    from sqlalchemy import create_engine

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
        echo=False,
    )
    restrict_file(sqlite_path(database_url))
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
