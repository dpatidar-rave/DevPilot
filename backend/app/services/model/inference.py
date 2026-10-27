"""Inference boundary. Review code depends on this protocol, not on a vendor client."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Protocol

from app.services.model.policy import KEEP_ALIVE


@dataclass(frozen=True)
class ModelOptions:
    """Local generation settings. The endpoint has already been forced to loopback."""

    model: str
    context_length: int
    temperature: float
    max_output_tokens: int
    timeout_seconds: float
    keep_alive: str = KEEP_ALIVE
    endpoint: str = "http://127.0.0.1:11434"
    large_model: bool = False


@dataclass(frozen=True)
class InferenceRequest:
    """One prompt for a local model. Callers must not log `prompt`."""

    prompt: str
    options: ModelOptions


class InferenceClient(Protocol):
    """A local model adapter. A different adapter can replace Ollama later."""

    def prepare(self, options: ModelOptions) -> None:
        """Fail if the model cannot run. Must not download weights."""

    def complete(self, request: InferenceRequest, cancel_event: threading.Event) -> str:
        """Return raw model text. The text is untrusted and must not be executed."""
