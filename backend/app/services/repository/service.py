"""Read-only git inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.security.command_gate import CommandOrigin, CommandRequest, authorize
from app.security.command_runner import CommandResult, CommandRunner


class RepositoryPathError(Exception):
    """The path is not a local git working tree DevPilot can inspect."""


@dataclass(frozen=True)
class DiffText:
    """Unified diff text. It is untrusted and must not be logged in full."""

    text: str
    truncated: bool


@dataclass(frozen=True)
class Inspection:
    """Text captured from allowlisted git commands. All fields are untrusted."""

    path: str
    inside_work_tree: bool
    branch: str
    status_porcelain: str
    truncated: bool


_STATUS_ARGV = ("git", "status", "--porcelain=v1", "--branch")
_INSIDE_ARGV = ("git", "rev-parse", "--is-inside-work-tree")
_BRANCH_ARGV = ("git", "symbolic-ref", "--short", "HEAD")
_DIFF_ARGV = ("git", "diff", "--no-ext-diff", "--no-textconv", "HEAD")
_MAX_STATUS_CHARS = 100_000
_MAX_DIFF_CHARS = 500_000


class RepositoryService:
    """Inspect a repository the user pointed at. Git is never mutated."""

    def __init__(self, runner: CommandRunner) -> None:
        self._runner = runner

    def inspect(self, path: str, *, approved: bool) -> Inspection:
        """Run the allowlisted inspection. `approved` must be an explicit user action."""
        authorize(
            CommandRequest(argv=_INSIDE_ARGV, approved=approved, origin=CommandOrigin.USER)
        )
        root = resolve_repository(path)
        inside = self._git(root, _INSIDE_ARGV, approved)
        branch = self._git(root, _BRANCH_ARGV, approved)
        status = self._git(root, _STATUS_ARGV, approved)
        inside_text = _single_line(inside)
        if inside_text not in {"true", "false"}:
            raise RepositoryPathError(
                "Git did not confirm this directory. The output was not executed."
            )
        branch_text = _single_line(branch)
        if branch_text == "":
            raise RepositoryPathError("Git did not return a branch name. Nothing else was executed.")
        porcelain, truncated = _cap(status.stdout)
        return Inspection(
            path=str(root),
            inside_work_tree=inside_text == "true",
            branch=branch_text,
            status_porcelain=porcelain,
            truncated=truncated,
        )

    def diff_against_head(self, path: str, *, approved: bool) -> DiffText:
        """Return `git diff HEAD` after an explicit approval. The diff is not logged."""
        authorize(CommandRequest(argv=_DIFF_ARGV, approved=approved, origin=CommandOrigin.USER))
        root = resolve_repository(path)
        result = self._git(root, _DIFF_ARGV, approved)
        text, truncated = _cap(result.stdout, _MAX_DIFF_CHARS)
        return DiffText(text=text, truncated=truncated)

    def _git(self, root: Path, argv: tuple[str, ...], approved: bool) -> CommandResult:
        result = self._runner.run(
            CommandRequest(argv=argv, approved=approved, origin=CommandOrigin.USER),
            root,
        )
        if result.exit_code != 0:
            detail = result.stderr.strip().splitlines()
            suffix = detail[0][:300] if detail else "Git exited with a non-zero status."
            raise RepositoryPathError(f"Git inspection failed. {suffix}")
        return result


def resolve_repository(path: str) -> Path:
    """Resolve a user-supplied absolute path and require a .git entry."""
    candidate = Path(path)
    if not candidate.is_absolute():
        raise RepositoryPathError("Repository path must be absolute.")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise RepositoryPathError("Repository path does not exist.") from exc
    if not resolved.is_dir():
        raise RepositoryPathError("Repository path must be a directory.")
    if not (resolved / ".git").exists():
        raise RepositoryPathError("Directory is not a Git repository (no .git entry).")
    return resolved


def _single_line(result: CommandResult) -> str:
    lines = result.stdout.splitlines()
    if len(lines) != 1:
        raise RepositoryPathError("Unexpected git output. Nothing else was executed.")
    return lines[0].strip()


def _cap(text: str, limit: int = _MAX_STATUS_CHARS) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    cut = text.rfind("\n", 0, limit)
    if cut <= 0:
        cut = limit
    return text[:cut], True
