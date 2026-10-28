"""Local Ollama client.

The review engine depends on InferenceClient, not on this class. Constructing
the gateway does not open a connection. Phase 0 has no method that sends a
request; a review in a later phase is the only caller that may.
"""

from __future__ import annotations

import threading
from typing import Protocol

import httpx

from app.config import Settings


class InferenceClient(Protocol):
    @property
    def model_name(self) -> str:
        """Name of the local model this client will use."""


class CancellationToken:
    """Cooperative cancellation for a single inference request."""

    def __init__(self) -> None:
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()


class ModelGateway:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.requests_made = 0
        self._limiter = threading.BoundedSemaphore(1)

    @property
    def model_name(self) -> str:
        return self._settings.model_name

    def client_options(self) -> dict[str, object]:
        """httpx options that cannot follow redirects or use a proxy environment."""
        return {
            "base_url": self._settings.ollama_endpoint,
            "timeout": self._settings.timeout_seconds,
            "trust_env": False,
            "follow_redirects": False,
            "max_connections": 1,
        }

    def open_client(self) -> httpx.Client:
        """Create a client. This does not send a request."""
        return httpx.Client(
            base_url=self._settings.ollama_endpoint,
            timeout=self._settings.timeout_seconds,
            trust_env=False,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )

    def try_reserve(self) -> bool:
        """Reserve the single inference slot. Does not contact Ollama."""
        return self._limiter.acquire(blocking=False)

    def release(self) -> None:
        self._limiter.release()
