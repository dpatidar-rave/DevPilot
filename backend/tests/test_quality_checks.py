"""Allowlisted quality checks. Every repository in this file is temporary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.quality import QualityCommand
from app.services.quality_policy import (
    QualityCommandError,
    detect_tools,
    validate_command,
)
from app.services.quality_runner import OUTPUT_LIMIT, QualityRunner, run_process

_PHPUNIT = ["php", "vendor/bin/phpunit", "--do-not-cache-result"]


def test_allowlist_rejects_destructive_and_shell_commands(tmp_path: Path) -> None:
    rejected = (
        ["php", "vendor/bin/phpcbf"],
        ["composer", "install"],
        ["composer", "update"],
        ["composer", "require", "magento/module-catalog"],
        ["composer", "config", "--unset", "name"],
        ["php", "-r", "echo 1;"],
        ["bash", "-c", "echo hi"],
        ["php", "bin/magento", "setup:upgrade"],
        ["php", "bin/magento", "setup:di:compile"],
        ["php", "bin/magento", "setup:static-content:deploy"],
        ["php", "bin/magento", "cache:flush"],
        ["php", "vendor/bin/phpunit", "&&", "rm", "-rf", "/"],
        ["/bin/sleep", "1"],
        ["php", "vendor/bin/phpstan", "analyse", "clear-result-cache"],
        ["php", "vendor/bin/phpunit", "app/code;id"],
    )
    for argv in rejected:
        with pytest.raises(QualityCommandError):
            validate_command(tmp_path, argv)


def test_argument_validation_keeps_paths_inside_the_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.php"
    outside.write_text("<?php echo 1;\n", encoding="utf-8")
    rejected = (
        ["php", "vendor/bin/phpunit", str(outside)],
        ["php", "vendor/bin/phpunit", "../outside.php"],
        ["php", "vendor/bin/phpcs", "app/../../outside.php"],
        ["composer", "validate", "--working-dir=/tmp"],
        ["composer", "validate"],
        ["php", "vendor/bin/phpstan", "clear-result-cache"],
        ["php", "bin/magento", "config:show"],
    )
    for argv in rejected:
        with pytest.raises(QualityCommandError):
            validate_command(repo, argv)
    assert outside.read_text(encoding="utf-8") == "<?php echo 1;\n"
    assert validate_command(repo, ["php", "vendor/bin/phpcs", "app/code"]) == "phpcs"
    assert (
        validate_command(repo, ["composer", "validate", "--no-check-publish", "--no-check-all"])
        == "composer"
    )


def test_detection_reads_files_and_does_not_start_a_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("A quality command started during detection.")

    monkeypatch.setattr("app.services.quality_runner._POPEN", boom)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "phpunit.xml").write_text("<phpunit/>\n", encoding="utf-8")
    (repo / "composer.json").write_text("{}\n", encoding="utf-8")
    (repo / "app" / "etc").mkdir(parents=True)
    (repo / "app" / "etc" / "di.xml").write_text("<config/>\n", encoding="utf-8")
    outside = tmp_path / "outside.php"
    outside.write_text("<?php echo 1;\n", encoding="utf-8")
    binary = repo / "vendor" / "bin"
    binary.mkdir(parents=True)
    (binary / "phpunit").symlink_to(outside)
    (binary / "phpcs").write_text("<?php echo 1;\n", encoding="utf-8")

    detected = {item.tool: item for item in detect_tools(repo)}

    assert detected["phpunit"].available is False
    assert "outside" in (detected["phpunit"].reason or "")
    assert detected["phpunit"].suggested_argv == ()
    assert "phpunit.xml" in detected["phpunit"].files
    assert "composer.json" in detected["composer"].files
    phpcs = detected["phpcs"]
    if phpcs.available:
        assert phpcs.suggested_argv[0] == "php"
    else:
        assert "PHP was not found" in (phpcs.reason or "")
    assert "app/etc/di.xml" in detected["magento"].files
    assert outside.read_text(encoding="utf-8") == "<?php echo 1;\n"


def test_runner_refuses_work_outside_the_repository(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("untouched", encoding="utf-8")

    def boom(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("A process started for a rejected command.")

    monkeypatch.setattr("app.services.quality_runner._POPEN", boom)
    runner = QualityRunner()
    with pytest.raises(QualityCommandError):
        runner.execute(["/bin/sleep", "1"], repo, 1, 1000, root=repo)
    with pytest.raises(QualityCommandError):
        runner.execute(
            ["/usr/bin/php", "vendor/bin/phpunit", "../outside.txt"],
            repo,
            1,
            1000,
            root=repo,
        )
    with pytest.raises(QualityCommandError):
        runner.execute(["/bin/echo", "hi"], tmp_path, 1, 1000, root=repo)
    assert runner.executions == 0
    assert outside.read_text(encoding="utf-8") == "untouched"


def test_process_starts_without_a_shell(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}
    real = subprocess.Popen

    def wrapped(argv: list[str], **kwargs: Any) -> subprocess.Popen[bytes]:
        seen["shell"] = kwargs.get("shell")
        seen["cwd"] = kwargs.get("cwd")
        return real(argv, **kwargs)

    monkeypatch.setattr("app.services.quality_runner._POPEN", wrapped)
    result = run_process(["/bin/echo", "ok"], tmp_path, 5, 1000)
    assert seen["shell"] is False
    assert seen["cwd"] == tmp_path
    assert result.exit_code == 0
    assert result.stdout.strip() == "ok"
    assert result.timed_out is False


def test_timeout_stops_the_process(tmp_path: Path) -> None:
    result = run_process(["/bin/sleep", "5"], tmp_path, 0.25, 1000)
    assert result.timed_out is True
    assert result.exit_code is None
    assert result.duration_ms < 3000
    assert result.working_directory == tmp_path.resolve().as_posix()


def test_oversized_output_is_truncated(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.write('x' * 200000); sys.stderr.write('y' * 200000)"
    result = run_process([sys.executable, "-c", code], tmp_path, 10, 1024)
    assert result.exit_code == 0
    assert result.truncated is True
    assert len(result.stdout.encode("utf-8")) <= 1024
    assert len(result.stderr.encode("utf-8")) <= 1024
    assert result.stdout.startswith("x")
    assert result.stderr.startswith("y")


def test_nonzero_exit_is_captured(tmp_path: Path) -> None:
    code = "import sys; sys.stdout.write('out'); sys.stderr.write('bad'); raise SystemExit(2)"
    result = run_process([sys.executable, "-c", code], tmp_path, 10, 1000)
    assert result.exit_code == 2
    assert result.timed_out is False
    assert result.stdout == "out"
    assert result.stderr == "bad"


def test_output_limit_cannot_be_removed(tmp_path: Path) -> None:
    with pytest.raises(QualityCommandError):
        run_process(["/bin/echo", "ok"], tmp_path, 1, OUTPUT_LIMIT + 1)


def test_unconfirmed_run_does_not_start_a_process(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
) -> None:
    _forbid_process(monkeypatch)
    project_id = _register(client, _repository(tmp_path))
    _save(client, project_id, _PHPUNIT)
    response = client.post(
        f"/api/projects/{project_id}/quality/runs",
        json={"tool": "phpunit", "confirmed": False},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Confirm the command before DevPilot runs it."
    assert app.state.quality_service.runner.executions == 0
    assert client.get("/api/quality-checks").json() == {"items": []}


def test_shell_text_from_the_request_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
) -> None:
    _forbid_process(monkeypatch)
    project_id = _register(client, _repository(tmp_path))
    response = client.post(
        f"/api/projects/{project_id}/quality/runs",
        json={"tool": "phpunit", "confirmed": True, "command": "rm -rf /"},
    )
    assert response.status_code == 422
    assert "rm -rf" not in response.text
    assert app.state.quality_service.runner.executions == 0


def test_saved_command_outside_the_repository_is_not_executed(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
) -> None:
    _forbid_process(monkeypatch)
    repo = _repository(tmp_path)
    outside = tmp_path / "outside.php"
    outside.write_text("<?php echo 'ran';\n", encoding="utf-8")
    project_id = _register(client, repo)
    rejected = client.put(
        f"/api/projects/{project_id}/quality/commands",
        json={"tool": "phpunit", "argv": ["php", "../outside.php"]},
    )
    assert rejected.status_code == 422
    _save(client, project_id, ["php", "vendor/bin/phpunit"])
    link = repo / "vendor" / "bin" / "phpunit"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    response = client.post(
        f"/api/projects/{project_id}/quality/runs",
        json={"tool": "phpunit", "confirmed": True},
    )
    assert response.status_code == 422
    assert app.state.quality_service.runner.executions == 0
    assert outside.read_text(encoding="utf-8") == "<?php echo 'ran';\n"


def test_missing_tool_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
) -> None:
    _forbid_process(monkeypatch)
    project_id = _register(client, _repository(tmp_path))
    _save(client, project_id, _PHPUNIT)
    response = client.post(
        f"/api/projects/{project_id}/quality/runs",
        json={"tool": "phpunit", "confirmed": True, "review_id": None},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result"] == "skipped"
    assert body["origin"] == "command_result"
    assert body["exit_code"] is None
    assert body["stdout"] == ""
    assert body["working_directory"]
    assert "php" in body["command"]
    assert app.state.quality_service.runner.executions == 0


def test_confirmed_run_stores_a_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)
    project_id = _register(client, repo)
    code = (
        "import sys; sys.stdout.write('SECRET_OUTPUT'); "
        "sys.stderr.write('bad'); raise SystemExit(2)"
    )
    outcome = run_process([sys.executable, "-c", code], repo, 10, 1000)
    body = _store_outcome(client, app, monkeypatch, project_id, outcome)
    assert body["result"] == "fail"
    assert body["status"] == "failed"
    assert body["exit_code"] == 2
    assert body["stdout"] == "SECRET_OUTPUT"
    assert body["stderr"] == "bad"
    assert body["origin"] == "command_result"
    assert body["duration_ms"] >= 0
    assert body["started_at"]
    log = Path(app.state.settings.log_dir) / "devpilot.log"
    assert "SECRET_OUTPUT" not in log.read_text(encoding="utf-8")


def test_confirmed_run_stores_a_timeout(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)
    project_id = _register(client, repo)
    outcome = run_process(["/bin/sleep", "5"], repo, 0.25, 1000)
    body = _store_outcome(client, app, monkeypatch, project_id, outcome)
    assert body["result"] == "timed_out"
    assert body["exit_code"] is None
    assert body["duration_ms"] < 3000


def test_confirmed_run_stores_truncated_output(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
) -> None:
    repo = _repository(tmp_path)
    project_id = _register(client, repo)
    code = "import sys; sys.stdout.write('z' * 200000)"
    outcome = run_process([sys.executable, "-c", code], repo, 10, 1024)
    body = _store_outcome(client, app, monkeypatch, project_id, outcome)
    assert body["output_truncated"] is True
    assert len(body["stdout"]) <= 1024
    assert body["result"] == "pass"


def test_registration_and_review_do_not_run_quality_commands(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
) -> None:
    _forbid_process(monkeypatch)

    class SilentModel:
        model_name = "qwen2.5-coder:7b"

        def complete(self, messages: list[dict[str, str]], cancel: object) -> str:
            del messages, cancel
            raise AssertionError("The review tried to run a quality command or a model.")

    repo = _repository(tmp_path)
    project_id = _register(client, repo)
    assert app.state.quality_service.runner.executions == 0
    app.state.review_service._synchronous = True
    app.state.review_service._inference = SilentModel()
    response = client.post(
        "/api/reviews",
        json={"project_id": project_id, "base_ref": "main", "paths": ["not-changed.php"]},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "completed"
    assert client.get("/api/quality-checks").json() == {"items": []}
    assert app.state.quality_service.runner.executions == 0


def test_corrupt_saved_command_is_not_executed(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
) -> None:
    _forbid_process(monkeypatch)
    project_id = _register(client, _repository(tmp_path))
    with app.state.session_factory() as session:
        session.add(
            QualityCommand(
                project_id=project_id,
                tool="phpunit",
                argv_json=json.dumps(["php", "../outside.php"]),
                updated_at=datetime.now(UTC),
            )
        )
        session.commit()
    response = client.post(
        f"/api/projects/{project_id}/quality/runs",
        json={"tool": "phpunit", "confirmed": True},
    )
    assert response.status_code == 422
    assert app.state.quality_service.runner.executions == 0


def _store_outcome(
    client: TestClient,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    project_id: str,
    outcome: object,
) -> dict[str, object]:
    _save(client, project_id, _PHPUNIT)
    monkeypatch.setattr(
        "app.services.quality_check.resolve_invocation",
        lambda repo, argv: ["/usr/bin/php", "vendor/bin/phpunit"],
    )

    class Runner(QualityRunner):
        def execute(
            self,
            argv: list[str],
            cwd: Path,
            timeout: float,
            output_limit: int = OUTPUT_LIMIT,
            root: Path | None = None,
        ) -> object:
            del argv, timeout, output_limit
            assert root is not None
            assert cwd.resolve() == root.resolve()
            self.executions += 1
            return outcome

    app.state.quality_service.runner = Runner()
    response = client.post(
        f"/api/projects/{project_id}/quality/runs",
        json={"tool": "phpunit", "confirmed": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, dict)
    return body


def _save(client: TestClient, project_id: str, argv: list[str]) -> None:
    response = client.put(
        f"/api/projects/{project_id}/quality/commands",
        json={"tool": "phpunit", "argv": argv},
    )
    assert response.status_code == 200, response.text


def _register(client: TestClient, repo: Path) -> str:
    response = client.post("/api/projects", json={"path": repo.as_posix(), "name": "Fixture"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert isinstance(body, dict)
    return str(body["id"])


def _repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    env = _git_env(tmp_path / "git-template")
    _init(repo, env)
    (repo / "app.php").write_text("<?php\necho 1;\n", encoding="utf-8")
    _git(repo, env, "add", "app.php")
    _git(repo, env, "commit", "-m", "base")
    return repo.resolve()


def _forbid_process(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("A quality command started.")

    monkeypatch.setattr("app.services.quality_runner._POPEN", boom)


def _init(repo: Path, env: dict[str, str]) -> None:
    repo.mkdir()
    _git(repo, env, "init", "-b", "main")


def _git(repo: Path, env: dict[str, str], *args: str) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr.decode("utf-8", errors="replace"))


def _git_env(template: Path) -> dict[str, str]:
    template.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "DevPilot Test",
            "GIT_AUTHOR_EMAIL": "devpilot@localhost",
            "GIT_COMMITTER_NAME": "DevPilot Test",
            "GIT_COMMITTER_EMAIL": "devpilot@localhost",
            "GIT_TEMPLATE_DIR": str(template),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
        }
    )
    env.pop("GIT_DIR", None)
    env.pop("GIT_WORK_TREE", None)
    return env
