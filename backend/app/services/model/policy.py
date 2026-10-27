"""Local model policy for a 16 GB Apple silicon machine.

This module names hosted model families so they can be rejected. It does not
call them.
"""

from __future__ import annotations

import re

DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_CONTEXT_LENGTH = 8192
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_OUTPUT_TOKENS = 1800
DEFAULT_TIMEOUT_SECONDS = 120.0
KEEP_ALIVE = "10m"
MAX_CONCURRENT_INFERENCE = 1
MIN_CONTEXT_LENGTH = 1024
MAX_CONTEXT_LENGTH = 8192
MIN_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 300.0

LARGE_MODEL_WARNING = (
    "This model is 20B or larger. On a 16 GB Apple silicon Mac it can exhaust memory. "
    "The default model is qwen2.5-coder:7b. Confirm this experiment before starting a review."
)

_CLOUD_FRAGMENTS = (
    "gpt-",
    "chatgpt",
    "claude",
    "anthropic",
    "gemini",
    "openai",
    "text-davinci",
    "text-embedding",
    "bedrock",
    "cohere",
)
_HOSTED_REASONING = re.compile(r"^o[0-9]($|[-.])")
_PARAMETER_SIZE = re.compile(r"(?:^|[^0-9])(\d{1,3})b(?:[^a-z0-9]|$)")


class ModelNameRejected(ValueError):
    """Raised when a model name is not a local Ollama tag."""


def assert_local_model_name(name: str) -> str:
    """Accept a local tag and reject hosted model names and endpoints."""
    cleaned = name.strip()
    if cleaned == "" or len(cleaned) > 128:
        raise ModelNameRejected("A local model name is required.")
    if any(character in cleaned for character in (" ", "/", "\\", "?", "#")) or "://" in cleaned:
        raise ModelNameRejected("Model names must be local Ollama tags, not endpoints.")
    lowered = cleaned.lower()
    if _HOSTED_REASONING.search(lowered) or any(fragment in lowered for fragment in _CLOUD_FRAGMENTS):
        raise ModelNameRejected(
            "That model name is a hosted model. DevPilot only runs a local Ollama tag."
        )
    return cleaned


def parameter_billions(name: str) -> int | None:
    """Return the parameter size encoded in an Ollama tag, when present."""
    match = _PARAMETER_SIZE.search(name.lower())
    if match is None:
        return None
    return int(match.group(1))


def is_large_model(name: str) -> bool:
    """20B and larger tags are optional memory experiments, not the default."""
    size = parameter_billions(name)
    return size is not None and size >= 20


def setup_instruction(model: str) -> str:
    """Tell the user how to install a model. This text is never executed."""
    local_name = assert_local_model_name(model)
    return (
        f"The local model {local_name} is not installed. "
        "DevPilot does not download models. "
        f"From a terminal, run `ollama pull {local_name}` and start the review again."
    )
