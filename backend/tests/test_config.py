"""Configuration stays on the local machine."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.security.loopback import (
    LOCAL_CORS_ORIGINS,
    LocalOnlyError,
    assert_local_sqlite,
    assert_loopback_host,
    assert_loopback_http_url,
)


def test_loopback_hosts_are_accepted() -> None:
    assert assert_loopback_host("127.0.0.1") == "127.0.0.1"
    assert assert_loopback_host(" localhost ") == "localhost"
    assert assert_loopback_http_url("http://127.0.0.1:11434/") == "http://127.0.0.1:11434"
    assert assert_loopback_http_url("http://[::1]:11434") == "http://[::1]:11434"


@pytest.mark.parametrize(
    "host",
    ["0.0.0.0", "192.168.1.20", "::", "example.com", ""],
)
def test_public_bind_host_is_rejected(host: str) -> None:
    with pytest.raises(LocalOnlyError):
        assert_loopback_host(host)


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "http://api.openai.com",
        "https://127.0.0.1:11434",
        "http://127.0.0.1:11434/api",
        "http://user:pass@127.0.0.1:11434",
        "http://10.0.0.5:11434",
    ],
)
def test_non_local_model_urls_are_rejected(url: str) -> None:
    with pytest.raises(LocalOnlyError):
        assert_loopback_http_url(url)


@pytest.mark.parametrize(
    "url",
    ["postgresql://localhost/devpilot", "http://127.0.0.1/devpilot.sqlite"],
)
def test_non_sqlite_databases_are_rejected(url: str) -> None:
    with pytest.raises(LocalOnlyError):
        assert_local_sqlite(url)


def test_memory_sqlite_is_allowed_for_tests() -> None:
    assert assert_local_sqlite("sqlite:///:memory:") == "sqlite:///:memory:"


def test_settings_reject_public_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVPILOT_HOST", "0.0.0.0")
    with pytest.raises(ValidationError):
        get_settings()


def test_settings_ignore_hosted_provider_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    settings = get_settings()
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.host == "127.0.0.1"


def test_direct_settings_reject_hosted_ollama_url() -> None:
    with pytest.raises(ValidationError):
        Settings(
            host="127.0.0.1",
            port=8000,
            database_url="sqlite:///:memory:",
            ollama_base_url="https://api.openai.com/v1",
        )


def test_cors_origins_are_loopback_only() -> None:
    assert "*" not in LOCAL_CORS_ORIGINS
    for origin in LOCAL_CORS_ORIGINS:
        assert origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")
