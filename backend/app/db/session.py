"""SQLite engine and session factory."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.security.loopback import assert_local_sqlite


def make_engine(database_url: str) -> Engine:
    """Create an engine for a local SQLite database."""
    assert_local_sqlite(database_url)
    return create_engine(database_url, connect_args={"check_same_thread": False}, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory that does not expire objects on commit."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
