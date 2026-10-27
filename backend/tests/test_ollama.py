"""Ollama failures stay failures."""

from __future__ import annotations

import threading

import httpx
import pytest

from app.security.loopback import OLLAMA_RETRY_INSTRUCTIONS
from app.services.model.errors import InferenceCancelled, InferenceTimeout
from app.services.model.ollama import GenerationSpec, OllamaClient, OllamaUnavailableError


def _spec(timeout: float = 2.0) -> GenerationSpec:
    return GenerationSpec(
        model="qwen2.5-coder:7b",
        prompt="review this",
        temperature=0.1,
        context_length=8192,
        max_output_tokens=1800,
        timeout_seconds=timeout,
        keep_alive="10m",
    )


def test_status_reads_local_model_names() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1"
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:7b"}, {"name": ""}]})

    client = OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    status = client.status()
    assert status.available is True
    assert status.endpoint == "http://127.0.0.1:11434"
    assert status.models == ("qwen2.5-coder:7b",)


def test_connection_error_includes_retry_and_does_not_retry_elsewhere() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        raise httpx.ConnectError("connection refused")

    client = OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaUnavailableError) as caught:
        client.status()
    assert seen == ["http://127.0.0.1:11434/api/tags"]
    assert "not running" in str(caught.value).lower() or "refused" in str(caught.value).lower()
    assert caught.value.retry == OLLAMA_RETRY_INSTRUCTIONS


def test_http_error_does_not_switch_provider() -> None:
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(500, text="nope")

    client = OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaUnavailableError) as caught:
        client.status()
    assert calls["count"] == 1
    assert "another provider" in str(caught.value).lower()


def test_redirect_is_not_followed() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://example.invalid/v1"})

    client = OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaUnavailableError) as caught:
        client.generate(_spec(), threading.Event())
    assert "redirect" in str(caught.value).lower()


def test_generate_stays_on_the_local_endpoint() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"response": "untrusted text"})

    client = OllamaClient("http://127.0.0.1:11434/", transport=httpx.MockTransport(handler))
    text = client.generate(_spec(), threading.Event())
    assert text == "untrusted text"
    assert seen == ["http://127.0.0.1:11434/api/generate"]
