"""Health endpoint and the contract the frontend reads."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings


def test_health_endpoint_reports_local_status(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["database"] == "ok"
    assert body["database_message"] is None
    assert body["bind_host"] == "127.0.0.1"
    assert body["ai"] == {
        "provider": "ollama",
        "endpoint": "http://127.0.0.1:11434",
        "model": "qwen2.5-coder:7b",
        "context_length": 8192,
        "temperature": 0.1,
        "max_output_tokens": 1800,
        "timeout_seconds": 180.0,
        "keep_alive": "10m",
        "max_concurrent_requests": 1,
        "availability": "not_checked",
        "external_providers": [],
        "large_model_confirmed": False,
    }
    assert "Traceback" not in response.text


def test_health_degrades_when_the_database_ping_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.api.health.ping", lambda _factory: False)

    response = client.get("/api/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"] == "error"
    assert "SQLite is unavailable" in body["database_message"]
    assert body["ai"]["provider"] == "ollama"
    assert body["ai"]["external_providers"] == []
    assert "Traceback" not in response.text


def test_request_log_keeps_query_secrets_out(client: TestClient, settings: Settings) -> None:
    token = "ghp_abcdefghijklmnopqrstuvwxyz"
    response = client.get("/api/health", params={"token": token})

    assert response.status_code == 200
    text = Path(settings.log_dir, "devpilot.log").read_text(encoding="utf-8")
    assert token not in text
    assert "/api/health" in text


def test_unknown_route_has_no_traceback(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert "Traceback" not in response.text


def test_interactive_docs_are_disabled(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    openapi = client.get("/api/openapi.json")
    assert openapi.status_code == 200
    assert "cdn" not in openapi.text.lower()
