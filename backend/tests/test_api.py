"""HTTP API for the local foundation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.model.ollama import OllamaClient
from app.services.persistence.service import NewReview


def _offline_ollama() -> OllamaClient:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"refused {request.url}")

    return OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))


def _ollama_with_models() -> OllamaClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1"
        return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:7b"}]})

    return OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))


@pytest.fixture()
def client(database_url: str) -> TestClient:
    application = create_app(ollama=_offline_ollama())
    assert application.state.container.settings.database_url == database_url
    return TestClient(application)


def test_health_is_local(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["bind_host"] == "127.0.0.1"
    assert body["data_store"] == "sqlite-local"
    assert body["ai_provider"] == "ollama-local"
    assert body["fallback_used"] is False


def test_status_does_not_contact_ollama(client: TestClient) -> None:
    response = client.get("/api/system/status")
    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is False
    assert body["ai_provider"] == "ollama-local"
    assert body["database"]["ready"] is True
    model = body["model"]
    assert model["name"] == "qwen2.5-coder:7b"
    assert model["context_length"] == 8192
    assert model["temperature"] == 0.1
    assert model["max_output_tokens"] == 1800
    assert model["timeout_seconds"] == 120
    assert model["keep_alive"] == "10m"
    assert model["endpoint"] == "http://127.0.0.1:11434"
    assert model["availability"] == "not_checked"
    assert model["large_model"] is False
    assert model["memory_warning"] is None


def test_ollama_models_are_not_required_for_status(database_url: str) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        raise AssertionError("status contacted Ollama")

    application = create_app(
        ollama=OllamaClient("http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
    )
    assert "devpilot.sqlite" in database_url
    response = TestClient(application).get("/api/system/status")
    assert response.status_code == 200
    assert calls == []
    assert response.json()["fallback_used"] is False


def test_empty_reviews_and_report(client: TestClient) -> None:
    reviews = client.get("/api/reviews")
    report = client.get("/api/release-report")
    assert reviews.status_code == 200
    assert reviews.json() == {"reviews": []}
    assert report.status_code == 200
    body = report.json()
    assert body["records"] == []
    assert body["summary"] == "No release report data is stored locally."
    assert "findings" not in body
    assert body["fallback_used"] is False


def test_release_report_returns_only_stored_rows(client: TestClient) -> None:
    client.app.state.container.persistence.save_review(
        NewReview(
            repository_path="/work/store",
            status="recorded",
            summary="stored-from-test-only",
        )
    )
    body = client.get("/api/release-report").json()
    assert body["summary"] == "1 locally stored review record(s)."
    assert len(body["records"]) == 1
    assert body["records"][0]["summary"] == "stored-from-test-only"


def test_quality_checks_are_not_executed(client: TestClient) -> None:
    body = client.get("/api/quality-checks").json()
    assert body["checks"]
    assert all(item["executed"] is False for item in body["checks"])
    assert all(item["execution"] == "disabled" for item in body["checks"])


def test_database_missing_migrations_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = f"sqlite:///{tmp_path / 'empty.sqlite'}"
    monkeypatch.setenv("DEVPILOT_DATABASE_URL", url)
    application = create_app(ollama=_offline_ollama())
    local_client = TestClient(application)
    status = local_client.get("/api/system/status")
    assert status.json()["database"]["ready"] is False
    assert status.json()["database"]["retry"]
    reviews = local_client.get("/api/reviews")
    assert reviews.status_code == 503
    assert reviews.json()["executed"] is False
    assert reviews.json()["retry"]


def test_cors_allows_localhost_and_rejects_other_origins(client: TestClient) -> None:
    allowed = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    rejected = client.options(
        "/api/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert rejected.headers.get("access-control-allow-origin") is None


def test_inspect_requires_approval_and_ignores_extra_commands(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("subprocess started")

    monkeypatch.setattr("app.security.command_runner.subprocess.run", fail_run)
    unapproved = client.post(
        "/api/repository/inspect",
        json={"path": "/tmp/not-used", "approved": False},
    )
    assert unapproved.status_code == 403
    assert unapproved.json()["executed"] is False
    extra = client.post(
        "/api/repository/inspect",
        json={"path": "/tmp/not-used", "approved": True, "argv": ["git", "push"]},
    )
    assert extra.status_code == 422
    missing = client.post("/api/repository/inspect", json={"path": "/tmp/not-used"})
    assert missing.status_code == 422


def test_inspect_read_only_git_status(client: TestClient, tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    marker = tmp_path / "alias-ran"
    fs_marker = tmp_path / "fs-ran"
    subprocess.run(
        ["git", "config", "alias.status", f"!echo ALIAS_RAN > {marker}"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "core.fsmonitor", f"!echo FS_RAN > {fs_marker}"],
        cwd=tmp_path,
        check=True,
    )
    response = client.post(
        "/api/repository/inspect",
        json={"path": str(tmp_path), "approved": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is True
    assert body["inside_work_tree"] is True
    assert body["status_porcelain"].startswith("##")
    assert marker.exists() is False
    assert fs_marker.exists() is False
    assert body["truncated"] is False


def test_relative_repository_path_is_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("subprocess started")

    monkeypatch.setattr("app.security.command_runner.subprocess.run", fail_run)
    response = client.post(
        "/api/repository/inspect",
        json={"path": "relative/repo", "approved": True},
    )
    assert response.status_code == 400
    assert response.json()["executed"] is False
