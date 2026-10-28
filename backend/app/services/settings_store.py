"""Persist the editable local model settings in SQLite."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.logging_config import log_event
from app.models.setting import AppSetting

SessionFactory = sessionmaker[Session]

ALLOWED_SETTING_KEYS = frozenset(
    {
        "model_name",
        "context_length",
        "temperature",
        "max_output_tokens",
        "timeout_seconds",
        "ollama_endpoint",
        "large_model_confirmed",
    }
)


def overlay_settings(base: Settings, session_factory: SessionFactory) -> Settings:
    """Apply stored keys on top of the environment. Invalid stored data fails closed."""
    with session_factory() as session:
        rows = list(session.scalars(select(AppSetting)))
    updates: dict[str, object] = {}
    for row in rows:
        if row.key not in ALLOWED_SETTING_KEYS:
            log_event(logging.WARNING, "ignored_setting", key=row.key)
            continue
        try:
            updates[row.key] = json.loads(row.value)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Stored setting {row.key!r} is unreadable. "
                "Fix the local app_settings table. "
                "DevPilot will not replace it with a hosted model."
            ) from exc
    if not updates:
        return base
    try:
        return Settings.model_validate({**base.model_dump(), **updates})
    except ValidationError as exc:
        messages = "; ".join(str(error["msg"]) for error in exc.errors())
        raise RuntimeError(
            "Stored local settings are invalid. "
            f"{messages} DevPilot will not replace them with a hosted model."
        ) from exc


def save_settings(session_factory: SessionFactory, changes: dict[str, object]) -> None:
    unknown = set(changes) - ALLOWED_SETTING_KEYS
    if unknown:
        raise ValueError("Only local model settings can be saved.")
    now = datetime.now(UTC)
    with session_factory() as session:
        for key, value in changes.items():
            existing = session.get(AppSetting, key)
            encoded = json.dumps(value)
            if existing is None:
                session.add(AppSetting(key=key, value=encoded, updated_at=now))
            else:
                existing.value = encoded
                existing.updated_at = now
        session.commit()


def replace_settings(current: Settings, changes: dict[str, object]) -> Settings:
    merged = current.model_dump()
    merged.update(changes)
    return Settings.model_validate(merged)
