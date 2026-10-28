"""Local logs drop secrets, prompts, and model responses."""

import logging
import stat
from pathlib import Path

from app.config import Settings
from app.logging_config import configure_logging, log_event, redact_text


def test_redacts_credentials() -> None:
    message = (
        'authorization=Bearer sk-supersecretvalue123456 '
        'token=ghp_abcdefghijklmnopqrstuvwxyz '
        '{"api_key": "sk-anothersecretvalue"}'
    )
    redacted = redact_text(message)
    assert "sk-supersecretvalue123456" not in redacted
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "sk-anothersecretvalue" not in redacted
    assert "[redacted]" in redacted


def test_log_file_omits_prompts_and_is_private(settings: Settings) -> None:
    path = configure_logging(settings)
    logging.getLogger("devpilot").info(
        "authorization=Bearer sk-supersecretvalue123456 token=ghp_abcdefghijklmnopqrstuvwxyz"
    )
    log_event(
        logging.INFO,
        "inference",
        prompt="print('full source')",
        response="full model response",
        diff="complete diff",
        model="qwen2.5-coder:7b",
    )

    text = Path(path).read_text(encoding="utf-8")
    assert "sk-supersecretvalue123456" not in text
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in text
    assert "print('full source')" not in text
    assert "full model response" not in text
    assert "complete diff" not in text
    assert "qwen2.5-coder:7b" in text
    assert "[redacted]" in text
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
