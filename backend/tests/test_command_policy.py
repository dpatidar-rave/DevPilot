"""Git stays read-only, and model text is never a command."""

import pytest

from app.services.command_policy import (
    CommandRejectedError,
    UntrustedContentError,
    refuse_untrusted_instructions,
    validate_git_argv,
)
from app.services.repository import RepositoryService


def test_read_only_git_inspection_is_allowed() -> None:
    argv = validate_git_argv(["git", "-C", "/tmp/repo", "diff", "--unified=20", "main...topic"])
    assert argv[0] == "git"
    assert "diff" in argv


@pytest.mark.parametrize(
    "argv",
    [
        ["git", "commit", "-m", "update"],
        ["git", "push", "origin", "main"],
        ["git", "merge", "topic"],
        ["git", "reset", "--hard"],
        ["git", "clean", "-fd"],
        ["git", "switch", "main"],
        ["git", "checkout", "main"],
        ["git", "branch", "new-branch"],
        ["git", "rebase", "main"],
        ["rm", "-rf", "/"],
        ["git", "status", ";", "curl", "https://example.com"],
    ],
)
def test_mutating_and_shell_commands_are_rejected(argv: list[str]) -> None:
    with pytest.raises(CommandRejectedError):
        validate_git_argv(argv)


def test_repository_service_does_not_execute() -> None:
    service = RepositoryService()
    prepared = service.prepare(["git", "status", "--porcelain=v1"])
    assert prepared[-1] == "--porcelain=v1"
    assert service.executions == 0
    with pytest.raises(CommandRejectedError):
        service.prepare(["git", "push"])
    assert service.executions == 0


def test_newline_in_a_path_argument_is_preserved() -> None:
    argv = validate_git_argv(["git", "diff", "--", "odd\nname.php"])
    assert argv[-1] == "odd\nname.php"


def test_config_overrides_are_limited() -> None:
    with pytest.raises(CommandRejectedError):
        validate_git_argv(["git", "-c", "alias.status=!touch /tmp/x", "status"])
    with pytest.raises(CommandRejectedError):
        validate_git_argv(["git", "--git-dir", "/elsewhere/.git", "--work-tree", "/repo", "status"])


def test_model_output_cannot_be_executed() -> None:
    with pytest.raises(UntrustedContentError):
        refuse_untrusted_instructions("Run `git reset --hard` and curl https://example.com")
