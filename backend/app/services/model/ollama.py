"""Local Ollama client. There is no hosted-model fallback and no model download."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from app.security.loopback import OLLAMA_RETRY_INSTRUCTIONS, assert_loopback_http_url
from app.services.model.errors import InferenceCancelled, InferenceTimeout
from app.services.model.policy import assert_local_model_name


class OllamaUnavailableError(Exception):
    """Ollama could not be used. Retry instructions are for the local daemon only."""

    def __init__(self, message: str, retry: tuple[str, ...] = OLLAMA_RETRY_INSTRUCTIONS) -> None:
        super().__init__(message)
        self.retry = tuple(retry)


@dataclass(frozen=True)
class OllamaStatus:
    """Result of a successful local model check."""

    available: bool
    endpoint: str
    models: tuple[str, ...]


@dataclass(frozen=True)
class GenerationSpec:
    """Generation options. `prompt` must not be written to logs."""

    model: str
    prompt: str
    temperature: float
    context_length: int
    max_output_tokens: int
    timeout_seconds: float
    keep_alive: str


class OllamaClient:
    """Talk only to a loopback Ollama HTTP endpoint."""

    def __init__(
        self,
        base_url: str,
        transport: Optional[httpx.BaseTransport] = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self.base_url = assert_loopback_http_url(base_url)
        self._transport = transport
        self._timeout = timeout_seconds
        self._client_lock = threading.Lock()
        self._active_client: Optional[httpx.Client] = None

    def status(self) -> OllamaStatus:
        """Read the local model list. This does not pull a model."""
        payload = self._request("GET", "/api/tags", None, self._timeout, threading.Event())
        models: list[str] = []
        raw_models = payload.get("models")
        if isinstance(raw_models, list):
            for item in raw_models:
                if isinstance(item, dict):
                    name = item.get("name")
                    if isinstance(name, str) and name:
                        models.append(name)
        return OllamaStatus(available=True, endpoint=self.base_url, models=tuple(models))

    def generate(self, spec: GenerationSpec, cancel_event: threading.Event) -> str:
        """Send one generation request to local Ollama and return raw text.

        The returned text is untrusted and must not be executed or logged.
        """
        assert_local_model_name(spec.model)
        if cancel_event.is_set():
            raise InferenceCancelled("The review was cancelled before the local model was called.")
        body = {
            "model": spec.model,
            "prompt": spec.prompt,
            "stream": False,
            "keep_alive": spec.keep_alive,
            "options": {
                "temperature": spec.temperature,
                "num_ctx": spec.context_length,
                "num_predict": spec.max_output_tokens,
            },
        }
        payload = self._request("POST", "/api/generate", body, spec.timeout_seconds, cancel_event)
        response_text = payload.get("response")
        if not isinstance(response_text, str):
            raise OllamaUnavailableError(
                "Ollama returned an unexpected response. Retry against the local daemon."
            )
        return response_text

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[dict[str, object]],
        timeout_seconds: float,
        cancel_event: threading.Event,
    ) -> dict[str, object]:
        outcome: dict[str, object] = {}

        def run() -> None:
            client: Optional[httpx.Client] = None
            try:
                client = httpx.Client(
                    transport=self._transport,
                    timeout=timeout_seconds,
                    follow_redirects=False,
                )
                with self._client_lock:
                    self._active_client = client
                response = client.request(method, self.base_url + path, json=body)
                outcome["response"] = response
            except Exception as exc:
                outcome["error"] = exc
            finally:
                with self._client_lock:
                    if self._active_client is client:
                        self._active_client = None
                if client is not None:
                    client.close()

        worker = threading.Thread(target=run, name="devpilot-ollama", daemon=True)
        worker.start()
        deadline = time.monotonic() + timeout_seconds
        while worker.is_alive():
            if cancel_event.is_set():
                self._close_active()
                worker.join(0.5)
                raise InferenceCancelled("The review was cancelled. The local request was stopped.")
            if time.monotonic() >= deadline:
                self._close_active()
                worker.join(0.5)
                raise InferenceTimeout("Local inference exceeded the configured timeout.")
            worker.join(0.05)
        if "error" in outcome:
            error = outcome["error"]
            if isinstance(error, httpx.HTTPError):
                raise OllamaUnavailableError(
                    "Ollama is not running on this machine, or the local endpoint refused the connection."
                ) from error
            if isinstance(error, Exception):
                raise OllamaUnavailableError(
                    "Ollama could not complete the local request."
                ) from error
            raise OllamaUnavailableError("Ollama could not complete the local request.")
        response = outcome.get("response")
        if not isinstance(response, httpx.Response):
            raise OllamaUnavailableError("Ollama returned an unexpected response.")
        if response.is_redirect:
            raise OllamaUnavailableError(
                "Ollama redirected the request. DevPilot does not follow redirects or change providers."
            )
        if response.status_code >= 400:
            raise OllamaUnavailableError(
                f"Ollama returned HTTP {response.status_code}. DevPilot did not try another provider."
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise OllamaUnavailableError(
                "Ollama returned a response that was not JSON. Retry the local daemon."
            ) from exc
        if not isinstance(payload, dict):
            raise OllamaUnavailableError("Ollama returned an unexpected response.")
        return payload

    def _close_active(self) -> None:
        with self._client_lock:
            client = self._active_client
        if client is not None:
            client.close()
