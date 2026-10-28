"""Hosted models and remote endpoints cannot be configured."""

from datetime import UTC
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import REPO_ROOT, Settings, get_settings
from app.services.model_gateway import CancellationToken, ModelGateway
from app.services.review import ReviewService


def test_defaults_are_the_local_7b_model(settings: Settings) -> None:
    assert settings.model_name == "qwen2.5-coder:7b"
    assert settings.context_length == 8192
    assert settings.temperature == 0.1
    assert settings.max_output_tokens == 1800
    assert settings.timeout_seconds == 180
    assert settings.keep_alive == "10m"
    assert settings.max_concurrent_inference == 1
    assert settings.large_model_confirmed is False
    assert settings.ollama_endpoint == "http://127.0.0.1:11434"
    assert "openai_api_key" not in Settings.model_fields
    assert "provider" not in Settings.model_fields


def test_environment_can_select_another_local_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVPILOT_MODEL", "qwen2.5-coder:14b")
    monkeypatch.setenv("DEVPILOT_CONTEXT_LENGTH", "4096")
    monkeypatch.setenv("DEVPILOT_TEMPERATURE", "0.2")
    monkeypatch.setenv("DEVPILOT_MAX_OUTPUT_TOKENS", "900")
    monkeypatch.setenv("DEVPILOT_TIMEOUT_SECONDS", "90")
    get_settings.cache_clear()

    selected = get_settings()

    assert selected.model_name == "qwen2.5-coder:14b"
    assert selected.context_length == 4096
    assert selected.temperature == 0.2
    assert selected.max_output_tokens == 900
    assert selected.timeout_seconds == 90


def test_hosted_model_names_are_rejected() -> None:
    hosted = (
        "gpt-4o",
        "claude-3-5-sonnet",
        "gemini-1.5-pro",
        "o1-mini",
        "text-embedding-3-large",
    )
    for name in hosted:
        with pytest.raises(ValidationError):
            Settings(_env_file=None, model_name=name)


def test_remote_endpoints_are_rejected() -> None:
    for endpoint in (
        "http://203.0.113.10:11434",
        "http://api.openai.com:11434",
        "http://10.1.2.3:11434",
        "http://127.0.0.1:11434/v1",
        "https://generativelanguage.googleapis.com:443",
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, ollama_endpoint=endpoint)


def test_localhost_endpoint_is_accepted() -> None:
    settings = Settings(_env_file=None, ollama_endpoint="http://localhost:11434")
    assert settings.ollama_endpoint == "http://localhost:11434"


def test_large_model_requires_an_explicit_confirmation() -> None:
    with pytest.raises(ValidationError, match="16 GB"):
        Settings(_env_file=None, model_name="qwen2.5-coder:20b")

    confirmed = Settings(
        _env_file=None,
        model_name="qwen2.5-coder:20b",
        large_model_confirmed=True,
    )
    assert confirmed.model_name == "qwen2.5-coder:20b"
    assert confirmed.large_model_confirmed is True


def test_concurrency_stays_at_one() -> None:
    with pytest.raises(ValidationError, match="must be 1"):
        Settings(_env_file=None, max_concurrent_inference=4)


def test_remote_database_is_rejected() -> None:
    with pytest.raises(ValidationError, match="SQLite"):
        Settings(_env_file=None, database_url="postgresql://db.example.com/devpilot")


def test_hosted_api_key_in_the_environment_is_ignored(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "sk-test-should-not-leak-0123456789"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert secret not in response.text
    assert response.json()["provider"] == "ollama"
    assert response.json()["external_providers"] == []
    assert response.json()["availability"] == "not_checked"


def _module_missing(name: str) -> bool:
    import importlib.util

    try:
        return importlib.util.find_spec(name) is None
    except ModuleNotFoundError:
        return True


def test_telemetry_export_is_disabled(app: FastAPI) -> None:
    import importlib.util

    assert app._telemetry["tracing"] is False
    assert app._telemetry["metrics"] is False
    assert app._telemetry["logs"] is False
    assert app._telemetry["operation_spans"] is False
    assert app._telemetry["auto_configure"] is False
    assert importlib.util.find_spec("opentelemetry.sdk") is None
    assert _module_missing("opentelemetry.exporter.otlp.proto.http.trace_exporter")


def test_manifests_do_not_depend_on_hosted_ai() -> None:
    backend = (REPO_ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8").lower()
    frontend = (REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8").lower()
    banned = (
        "openai",
        "anthropic",
        "cohere",
        "groq",
        "google-generativeai",
        "sentry-sdk",
        "posthog",
        "@sentry",
    )
    for name in banned:
        assert name not in backend
        assert name not in frontend


def test_gateway_does_not_send_and_review_can_use_another_client(
    settings: Settings,
    app: FastAPI,
) -> None:
    gateway = ModelGateway(settings)
    options = gateway.client_options()
    assert options["trust_env"] is False
    assert options["follow_redirects"] is False
    assert options["max_connections"] == 1
    client = gateway.open_client()
    try:
        assert client.follow_redirects is False
        assert client.trust_env is False
    finally:
        client.close()
    assert gateway.requests_made == 0
    assert gateway.try_reserve() is True
    assert gateway.try_reserve() is False
    gateway.release()

    token = CancellationToken()
    assert token.is_cancelled() is False
    token.cancel()
    assert token.is_cancelled() is True

    class FakeInference:
        @property
        def model_name(self) -> str:
            return "fake-local"

    review = ReviewService(FakeInference(), app.state.session_factory)
    assert review.inference.model_name == "fake-local"
    assert gateway.model_name == "qwen2.5-coder:7b"


def test_stored_cloud_setting_is_not_returned(app: FastAPI) -> None:
    from datetime import datetime

    from app.models.setting import AppSetting

    with app.state.session_factory() as session:
        session.add(
            AppSetting(
                key="openai_api_key",
                value='"sk-stored-should-not-leak"',
                updated_at=datetime.now(UTC),
            )
        )
        session.commit()

    # Rebuild so startup overlay runs against the stored row.
    from app.main import create_app

    restarted = create_app(app.state.settings)
    try:
        with TestClient(restarted, base_url="http://127.0.0.1") as restarted_client:
            body = restarted_client.get("/api/settings").json()
    finally:
        restarted.state.engine.dispose()

    assert "sk-stored-should-not-leak" not in str(body)
    assert body["provider"] == "ollama"
    log_text = Path(app.state.settings.log_dir, "devpilot.log").read_text(encoding="utf-8")
    assert "sk-stored-should-not-leak" not in log_text
