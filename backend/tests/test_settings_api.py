"""Editable local model settings."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_patch_persists_local_model_settings(settings: Settings, client: TestClient) -> None:
    response = client.patch(
        "/api/settings",
        json={
            "model": "qwen2.5-coder:14b",
            "context_length": 4096,
            "temperature": 0.2,
            "max_output_tokens": 1200,
            "timeout_seconds": 90,
            "ollama_endpoint": "http://127.0.0.1:11434",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "qwen2.5-coder:14b"
    assert body["context_length"] == 4096
    assert body["temperature"] == 0.2
    assert body["provider"] == "ollama"
    assert body["max_concurrent_requests"] == 1

    restarted = create_app(settings)
    try:
        with TestClient(restarted, base_url="http://127.0.0.1") as restarted_client:
            persisted = restarted_client.get("/api/settings").json()
    finally:
        restarted.state.engine.dispose()

    assert persisted["model"] == "qwen2.5-coder:14b"
    assert persisted["temperature"] == 0.2


def test_patch_rejects_a_hosted_model_and_a_remote_endpoint(client: TestClient) -> None:
    hosted = client.patch("/api/settings", json={"model": "gpt-4o"})
    remote = client.patch(
        "/api/settings",
        json={"ollama_endpoint": "http://203.0.113.10:11434"},
    )
    extra = client.patch("/api/settings", json={"provider": "openai"})

    assert hosted.status_code == 422
    assert "Hosted model names are not allowed" in hosted.text
    assert remote.status_code == 422
    assert "loopback" in remote.text
    assert extra.status_code == 422
    assert "gpt-4o" not in client.get("/api/settings").json()["model"]
    assert client.get("/api/settings").json()["model"] == "qwen2.5-coder:7b"


def test_large_model_patch_requires_confirmation(client: TestClient) -> None:
    rejected = client.patch("/api/settings", json={"model": "qwen2.5-coder:32b"})
    accepted = client.patch(
        "/api/settings",
        json={"model": "qwen2.5-coder:32b", "large_model_confirmed": True},
    )

    assert rejected.status_code == 422
    assert "16 GB" in rejected.text
    assert accepted.status_code == 200
    assert accepted.json()["model"] == "qwen2.5-coder:32b"
    assert accepted.json()["large_model_confirmed"] is True
