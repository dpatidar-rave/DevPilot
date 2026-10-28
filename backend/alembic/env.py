"""Alembic environment. The application passes the SQLite URL in."""

import logging
from collections.abc import Mapping

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.base import Base
from app.models import AppSetting, Project, QualityCheckRun, ReleaseReport, Review, ReviewFinding

_REGISTERED_MODELS = (
    AppSetting,
    Project,
    QualityCheckRun,
    ReleaseReport,
    Review,
    ReviewFinding,
)
_registered_tables = {model.__tablename__ for model in _REGISTERED_MODELS}
if _registered_tables != set(Base.metadata.tables):
    raise RuntimeError("SQLAlchemy metadata does not match the imported models.")

config = context.config
logging.getLogger("alembic").setLevel(logging.WARNING)
target_metadata = Base.metadata


def get_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("sqlalchemy.url is not set.")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section)
    configuration: dict[str, str] = dict(section) if isinstance(section, Mapping) else {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
