"""Startup and source boundaries."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.__main__ import main
from app.security.loopback import LocalOnlyError

_ROOT = Path(__file__).resolve().parents[2]
_APP = _ROOT / "backend" / "app"
_FRONTEND = _ROOT / "frontend" / "src"
_BANNED = (
    "openai",
    "anthropic",
    "sentry",
    "posthog",
    "googletagmanager",
    "generativelanguage",
    "telemetry",
    "api.openai.com",
)


def test_cli_binds_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    import uvicorn

    monkeypatch.setattr(uvicorn, "run", fake_run)
    main([])
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["reload"] is False
    assert kwargs["port"] == 8000


def test_cli_rejects_public_host() -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--host", "0.0.0.0"])
    assert "localhost" in str(caught.value).lower() or "refusing" in str(caught.value).lower()


def test_subprocess_is_isolated_to_the_runner() -> None:
    for path in _APP.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "shell=True" not in text
        assert "os.system" not in text
        if path.name == "command_runner.py":
            assert "shell=False" in text
            continue
        assert "subprocess" not in text, path


def test_routes_do_not_call_the_model() -> None:
    source = (_APP / "api" / "routes.py").read_text(encoding="utf-8")
    assert ".generate(" not in source


def test_source_has_no_remote_services() -> None:
    roots = [_APP, _FRONTEND]
    for root in roots:
        assert root.is_dir(), root
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx", ".css", ".html"}:
                continue
            text = path.read_text(encoding="utf-8").lower()
            if path.name == "policy.py":
                assert "https://" not in text
                assert "http://" not in text
                continue
            for banned in _BANNED:
                assert banned not in text, f"{banned} found in {path}"
            assert "dangerouslysetinnerhtml" not in text


def test_vite_binds_loopback() -> None:
    text = (_ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    assert 'host: "127.0.0.1"' in text
    assert "0.0.0.0" not in text
    assert "https://" not in text


def test_local_only_error_is_an_exception() -> None:
    assert issubclass(LocalOnlyError, ValueError)
