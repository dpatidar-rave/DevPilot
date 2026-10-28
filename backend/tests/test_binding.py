"""The API listens on loopback and the browser origin is local."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.main import serve

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_default_bind_host_is_loopback(settings: Settings) -> None:
    assert settings.host == "127.0.0.1"
    assert settings.frontend_origin == "http://127.0.0.1:5173"


def test_public_and_wildcard_hosts_are_rejected() -> None:
    from app.config import Settings

    for host in ("0.0.0.0", "192.168.1.20", "example.com", "*"):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, host=host)


def test_remote_frontend_origin_is_rejected() -> None:
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, frontend_origin="https://review.example.com")


def test_serve_uses_the_loopback_host(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(*_args: object, **kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("app.main.uvicorn.run", fake_run)
    serve()

    assert captured["host"] == "127.0.0.1"
    assert captured["proxy_headers"] is False
    assert captured["access_log"] is False
    assert captured["factory"] is True


def test_serve_refuses_a_public_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVPILOT_HOST", "0.0.0.0")
    get_settings.cache_clear()
    called = False

    def fake_run(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("app.main.uvicorn.run", fake_run)
    with pytest.raises(SystemExit) as caught:
        serve()

    assert caught.value.code == 1
    assert called is False


def test_cors_allows_the_local_ui_and_rejects_other_origins(client: TestClient) -> None:
    allowed = client.get("/api/health", headers={"Origin": "http://127.0.0.1:5173"})
    alias = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    blocked = client.get("/api/health", headers={"Origin": "https://review.example.com"})

    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert alias.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in blocked.headers
    assert allowed.headers["access-control-allow-origin"] != "*"


def test_preflight_from_the_frontend_origin(client: TestClient) -> None:
    response = client.options(
        "/api/settings",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert "PATCH" in response.headers["access-control-allow-methods"]


def test_untrusted_host_header_is_rejected(client: TestClient) -> None:
    response = client.get("/api/health", headers={"Host": "review.example.com"})

    assert response.status_code == 400


def test_running_server_binds_loopback_only(tmp_path: Path) -> None:
    port = _free_port()
    database = tmp_path / "server.db"
    log_dir = tmp_path / "logs"
    output = tmp_path / "server.out"
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "PYTHONUNBUFFERED": "1",
        "DEVPILOT_DISABLE_ENV_FILE": "1",
        "DEVPILOT_HOST": "127.0.0.1",
        "DEVPILOT_PORT": str(port),
        "DEVPILOT_DATABASE_URL": f"sqlite:///{database}",
        "DEVPILOT_LOG_DIR": str(log_dir),
    }
    handle = output.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "app"],
        cwd=BACKEND_DIR,
        env=env,
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_health(port, process, output)
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
        lan = _lan_ip()
        if lan is not None:
            refused = socket.socket()
            refused.settimeout(0.4)
            try:
                refused.connect((lan, port))
            except OSError:
                pass
            else:
                pytest.fail(f"The server accepted a connection on {lan}:{port}")
            finally:
                refused.close()
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        handle.close()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(port: int, process: subprocess.Popen[str], output: Path) -> None:
    deadline = time.time() + 20
    while time.time() < deadline:
        if process.poll() is not None:
            break
        try:
            health_url = f"http://127.0.0.1:{port}/api/health"
            with urllib.request.urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.1)
    raise AssertionError(output.read_text(encoding="utf-8"))


def _lan_ip() -> str | None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        address = str(probe.getsockname()[0])
    except OSError:
        return None
    finally:
        probe.close()
    if address.startswith("127."):
        return None
    return address
