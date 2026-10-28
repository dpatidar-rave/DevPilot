"""JSON logs on the local disk, with secrets and review content removed."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings

_LOGGER_NAME = "devpilot"
_MAX_FIELD_LENGTH = 300
_BLOCKED_FIELDS = frozenset(
    {
        "prompt",
        "prompts",
        "completion",
        "response",
        "diff",
        "source",
        "patch",
        "content",
        "code",
        "file_contents",
        "messages",
        "stdout",
        "stderr",
        "authorization",
        "api_key",
        "token",
        "secret",
        "password",
        "credential",
    }
)
_SECRET_PATTERNS = (
    re.compile(
        r"(?i)([\"']?(?:authorization|api[_-]?key|token|secret|password|credential)[\"']?"
        r"\s*[:=]\s*[\"']?)([^\s\"',}]+)"
    ),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{8,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def redact_text(value: str) -> str:
    """Replace credential-shaped text. The replacement is stable for tests."""
    redacted = value
    for pattern in _SECRET_PATTERNS:
        if pattern.groups == 2:
            redacted = pattern.sub(r"\1[redacted]", redacted)
        else:
            redacted = pattern.sub("[redacted]", redacted)
    return redacted


def sanitize_fields(fields: Mapping[str, object]) -> dict[str, object]:
    """Drop source, prompts, and model responses before they reach a handler."""
    clean: dict[str, object] = {}
    for key, value in fields.items():
        if key.lower() in _BLOCKED_FIELDS:
            clean[key] = "[redacted]"
            continue
        if isinstance(value, str):
            text = value
        elif isinstance(value, (int, float, bool)) or value is None:
            clean[key] = value
            continue
        else:
            text = json.dumps(value, default=str)
        text = redact_text(text)
        if len(text) > _MAX_FIELD_LENGTH:
            text = text[:_MAX_FIELD_LENGTH] + "…"
        clean[key] = text
    return clean


def log_event(level: int, event: str, **fields: object) -> None:
    payload = {"event": event, **sanitize_fields(fields)}
    logging.getLogger(_LOGGER_NAME).log(level, json.dumps(payload, sort_keys=True, default=str))


class RedactingJsonFormatter(logging.Formatter):
    """Format one JSON object per line and redact the rendered message."""

    def format(self, record: logging.LogRecord) -> str:
        message = redact_text(record.getMessage())
        if record.exc_info:
            message = f"{message} | {redact_text(self.formatException(record.exc_info))}"
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
        }
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(settings: Settings) -> Path:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "devpilot.log"
    logger = logging.getLogger(_LOGGER_NAME)
    logger.handlers.clear()
    logger.setLevel(settings.log_level)
    logger.propagate = False
    formatter = RedactingJsonFormatter()
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    if log_path.exists():
        log_path.chmod(0o600)
    return log_path
