"""Isolated local settings for every test."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key in list(os.environ):
        if key.startswith("DEVPILOT_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DEVPILOT_DISABLE_ENV_FILE", "1")
    monkeypatch.setenv("DEVPILOT_DATABASE_URL", f"sqlite:///{tmp_path / 'devpilot.db'}")
    monkeypatch.setenv("DEVPILOT_LOG_DIR", str(tmp_path / "logs"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def block_ollama(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[object]]:
    """Fail the test if application code opens a connection to Ollama."""
    attempts: list[object] = []
    original = socket.socket.connect

    def connect(self: socket.socket, address: object) -> None:
        port = address[1] if isinstance(address, tuple) and len(address) > 1 else None
        if port == 11434:
            attempts.append(address)
            raise AssertionError(f"DevPilot contacted Ollama at {address}")
        original(self, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    yield attempts
    assert attempts == []


@pytest.fixture
def settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def app(settings: Settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="http://127.0.0.1") as test_client:
        yield test_client
