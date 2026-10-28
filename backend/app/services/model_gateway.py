"""Local Ollama client.

The review engine depends on InferenceClient, not on this class. Constructing
the gateway does not open a connection. complete() is the only method that
sends a request, and it sends that request only to the configured loopback
Ollama origin.
"""

from __future__ import annotations

import json
import threading
from typing import Protocol

import httpx

from app.config import Settings
from app.local_policy import validate_ollama_endpoint


class InferenceError(Exception):
    """A local inference failure. The message is a short code, never a prompt."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class InferenceClient(Protocol):
    @property
    def model_name(self) -> str:
        """Name of the local model this client will use."""

    def complete(self, messages: list[dict[str, str]], cancel: CancellationToken) -> str:
        """Return the model text. Implementations must not call a remote provider."""


class CancellationToken:
    """Cooperative cancellation for a single inference request."""

    def __init__(self) -> None:
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()


class ModelGateway:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._transport = transport
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
            transport=self._transport,
        )

    def try_reserve(self) -> bool:
        """Reserve the single inference slot. Does not contact Ollama."""
        return self._limiter.acquire(blocking=False)

    def release(self) -> None:
        self._limiter.release()

    def complete(self, messages: list[dict[str, str]], cancel: CancellationToken) -> str:
        """Send one chat request to local Ollama. Redirects and proxies stay off."""
        validate_ollama_endpoint(self._settings.ollama_endpoint)
        if self._settings.model_name.strip() == "":
            raise InferenceError("model_missing")
        if cancel.is_cancelled():
            raise InferenceError("cancelled")
        if not self.try_reserve():
            raise InferenceError("busy")
        try:
            self.requests_made += 1
            payload = {
                "model": self._settings.model_name,
                "messages": messages,
                "stream": False,
                "format": "json",
                "keep_alive": self._settings.keep_alive,
                "options": {
                    "temperature": self._settings.temperature,
                    "num_ctx": self._settings.context_length,
                    "num_predict": self._settings.max_output_tokens,
                },
            }
            try:
                with self.open_client() as client:
                    response = client.post("/api/chat", json=payload)
            except httpx.TimeoutException as exc:
                raise InferenceError("timeout") from exc
            except httpx.HTTPError as exc:
                raise InferenceError("unavailable") from exc
            return _chat_text(response)
        finally:
            self.release()


def _chat_text(response: httpx.Response) -> str:
    if response.status_code == 404:
        raise InferenceError("model_missing")
    if response.is_redirect or response.status_code != 200:
        raise InferenceError("unavailable")
    try:
        parsed = json.loads(response.content[:200_000])
    except json.JSONDecodeError as exc:
        raise InferenceError("malformed") from exc
    if not isinstance(parsed, dict):
        raise InferenceError("malformed")
    error = parsed.get("error")
    if isinstance(error, str) and "not found" in error.lower():
        raise InferenceError("model_missing")
    message = parsed.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or content.strip() == "":
        raise InferenceError("malformed")
    return content
