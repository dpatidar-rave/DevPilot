"""The process runner rejects anything that is not an approved read-only inspection."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.security.command_gate import CommandOrigin, CommandRejected, CommandRequest, authorize
from app.security.command_runner import CommandRunner
from app.security.git_policy import build_safe_git_argv


def test_model_and_repository_origins_are_rejected(tmp_path: Path) -> None:
    for origin in (CommandOrigin.MODEL, CommandOrigin.REPOSITORY):
        request = CommandRequest(
            argv=("git", "status", "--porcelain=v1", "--branch"),
            approved=True,
            origin=origin,
        )
        with pytest.raises(CommandRejected):
            authorize(request)
        with pytest.raises(CommandRejected):
            CommandRunner().run(request, tmp_path)


@pytest.mark.parametrize(
    "argv",
    [
        ("git", "push"),
        ("git", "commit", "-m", "x"),
        ("git", "reset", "--hard"),
        ("git", "clean", "-fd"),
        ("git", "checkout", "main"),
        ("git", "switch", "main"),
        ("git", "merge", "main"),
        ("git", "status"),
        ("git", "status", "--porcelain=v1", "--branch", "--ignored"),
        ("git", "-c", "core.fsmonitor=!touch /tmp/x", "status", "--porcelain=v1", "--branch"),
    ],
)
def test_mutating_or_unlisted_git_is_rejected(argv: tuple[str, ...]) -> None:
    with pytest.raises(CommandRejected):
        build_safe_git_argv(argv)


def test_allowlisted_status_is_hardened() -> None:
    argv = build_safe_git_argv(("git", "status", "--porcelain=v1", "--branch"))
    assert argv[0] == "git"
    assert "--no-optional-locks" in argv
    assert "alias.status=" in argv
    assert "core.fsmonitor=" in argv
    assert argv[-3:] == ["status", "--porcelain=v1", "--branch"]


def test_unapproved_command_does_not_start_a_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("subprocess started")

    monkeypatch.setattr("app.security.command_runner.subprocess.run", fail_run)
    with pytest.raises(CommandRejected):
        CommandRunner().run(
            CommandRequest(
                argv=("git", "status", "--porcelain=v1", "--branch"),
                approved=False,
                origin=CommandOrigin.USER,
            ),
            tmp_path,
        )


def test_runner_uses_a_fixed_argument_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(argv: list[str], **kwargs: object) -> object:
        captured["argv"] = argv
        captured["kwargs"] = kwargs

        class Completed:
            returncode = 0
            stdout = "true\n"
            stderr = ""

        return Completed()

    monkeypatch.setattr("app.security.command_runner.subprocess.run", fake_run)
    result = CommandRunner().run(
        CommandRequest(
            argv=("git", "rev-parse", "--is-inside-work-tree"),
            approved=True,
            origin=CommandOrigin.USER,
        ),
        tmp_path,
    )
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert result.stdout == "true\n"
    assert kwargs["shell"] is False
    assert kwargs["stdin"] is subprocess.DEVNULL
    argv = captured["argv"]
    assert isinstance(argv, list)
    assert argv[0] == "git"
    assert "alias.rev-parse=" in argv
    env = kwargs["env"]
    assert isinstance(env, dict)
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert "OPENAI_API_KEY" not in env
    assert "GIT_EXTERNAL_DIFF" not in env
