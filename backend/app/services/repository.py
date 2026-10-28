"""Read-only inspection of registered Git working trees."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.logging_config import redact_text
from app.services.command_policy import CommandRejectedError, validate_git_argv
from app.services.git_runner import GitError, GitOutput, GitRunner
from app.services.magento_project import MagentoInfo, detect_magento
from app.services.path_safety import PathClass, classify_relative, normalize_relative

_DIFF_BYTES = 200_000
_DIFF_LINES = 1_500
_LINE_CHARS = 2_000
_LIST_LIMIT = 400
_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,200}$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
_LANGUAGES = {
    ".php": "php",
    ".phtml": "php",
    ".xml": "xml",
    ".html": "xml",
    ".json": "json",
    ".js": "javascript",
    ".mjs": "javascript",
    ".css": "css",
    ".less": "css",
    ".scss": "scss",
    ".sql": "sql",
    ".ini": "ini",
    ".sh": "bash",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".md": "markdown",
}
_SCOPES = frozenset({"staged", "unstaged", "committed", "untracked"})
UNCOMMITTED_WARNING = (
    "This repository has uncommitted changes. "
    "DevPilot will not commit, discard, or switch branches."
)


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    subject: str
    committed_at: str | None


@dataclass(frozen=True)
class Inspection:
    branch: str | None
    detached: bool
    head: CommitInfo | None
    branches: list[str]
    dirty: bool
    magento: MagentoInfo


@dataclass(frozen=True)
class ChangeFile:
    path: str
    status: str
    skipped: str | None


@dataclass(frozen=True)
class ChangeGroups:
    base: str | None
    branches: list[str]
    staged: list[ChangeFile]
    unstaged: list[ChangeFile]
    committed: list[ChangeFile]
    untracked: list[ChangeFile]
    truncated: bool

    @property
    def dirty(self) -> bool:
        return bool(self.staged or self.unstaged or self.untracked)

    def paths_for(self, scope: str) -> set[str]:
        return {item.path for item in self._group(scope)}

    def _group(self, scope: str) -> list[ChangeFile]:
        if scope == "staged":
            return self.staged
        if scope == "unstaged":
            return self.unstaged
        if scope == "committed":
            return self.committed
        return self.untracked


@dataclass(frozen=True)
class DiffLine:
    kind: str
    text: str
    old_line: int | None
    new_line: int | None


@dataclass(frozen=True)
class FileDiff:
    path: str
    scope: str
    binary: bool
    truncated: bool
    skipped: str | None
    language: str | None
    lines: list[DiffLine]


@dataclass(frozen=True)
class DirectoryListing:
    path: str
    parent: str | None
    directories: list[str]
    truncated: bool


@dataclass(frozen=True)
class _RawChange:
    status: str
    path: str


class RepositoryService:
    """Validates git argument lists and runs only read-only inspection."""

    def __init__(self, runner: GitRunner | None = None) -> None:
        self.executions = 0
        self._runner = runner or GitRunner()

    def prepare(self, argv: list[str]) -> list[str]:
        """Validate a git command. This does not execute it."""
        return validate_git_argv(argv)

    def list_directories(self, raw_path: str | None) -> DirectoryListing:
        if raw_path is None or raw_path == "":
            current = Path.home().resolve()
        else:
            current = resolve_directory(raw_path)
        parent = None if current.parent == current else current.parent.as_posix()
        found: list[str] = []
        try:
            entries = list(current.iterdir())
        except OSError as exc:
            raise GitError("DevPilot cannot list that directory.", 403) from exc
        for entry in entries:
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_symlink() or not entry.is_dir():
                    continue
            except OSError:
                continue
            found.append(entry.name)
            if len(found) >= 2000:
                break
        found.sort(key=str.casefold)
        return DirectoryListing(current.as_posix(), parent, found[:300], len(found) > 300)

    def ensure_work_tree(self, raw_path: str) -> Path:
        repo = resolve_directory(raw_path)
        self._require_git_dir(repo)
        inside = self._git(repo, ["rev-parse", "--is-inside-work-tree"])
        toplevel = self._git(repo, ["rev-parse", "--show-toplevel"])
        if inside.code != 0 or inside.stdout.strip() != b"true" or toplevel.code != 0:
            raise GitError("That folder is not a Git working tree.")
        reported = _decode(toplevel.stdout.strip())
        if reported is None or Path(reported).resolve() != repo:
            raise GitError("That folder is not the root of a Git working tree.")
        return repo

    def ensure_registered(self, stored_path: str) -> Path:
        try:
            current = Path(stored_path).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise GitError("The registered folder is no longer available.") from exc
        if current.as_posix() != stored_path:
            raise GitError("The registered path no longer points at the same directory.")
        return self.ensure_work_tree(stored_path)

    def display_name(self, repo: Path, requested: str | None) -> str:
        name = repo.name if requested is None or requested.strip() == "" else requested.strip()
        if name == "" or len(name) > 200 or any(ord(char) < 32 for char in name):
            raise GitError("Repository name must be plain text up to 200 characters.", 422)
        return name

    def inspect(self, repo: Path) -> Inspection:
        branch, detached = self._branch(repo)
        return Inspection(
            branch=branch,
            detached=detached,
            head=self._head(repo),
            branches=self._branches(repo),
            dirty=self._dirty(repo),
            magento=detect_magento(repo),
        )

    def changes(self, repo: Path, requested_base: str | None) -> ChangeGroups:
        branch, _detached = self._branch(repo)
        branches = self._branches(repo)
        base = choose_base(requested_base, branches, branch)
        staged, staged_cut = _cap(self._raw(repo, ["diff", "--cached", *_raw_diff_args()]))
        unstaged, unstaged_cut = _cap(self._raw(repo, ["diff", *_raw_diff_args()]))
        committed: list[_RawChange] = []
        committed_cut = False
        if base is not None and self._has_head(repo):
            committed, committed_cut = _cap(
                self._raw(repo, ["diff", *_raw_diff_args(), f"{base}...HEAD"])
            )
        untracked, untracked_cut = _cap(self._untracked(repo))
        return ChangeGroups(
            base=base,
            branches=branches,
            staged=[_change_file(item) for item in staged],
            unstaged=[_change_file(item) for item in unstaged],
            committed=[_change_file(item) for item in committed],
            untracked=[_change_file(item) for item in untracked],
            truncated=staged_cut or unstaged_cut or committed_cut or untracked_cut,
        )

    def file_diff(
        self,
        repo: Path,
        scope: str,
        relative: str,
        requested_base: str | None,
    ) -> FileDiff:
        if scope not in _SCOPES:
            raise GitError("Choose staged, unstaged, committed, or untracked changes.", 422)
        normalized = normalize_relative(relative)
        if normalized is None:
            raise GitError("That file path is not inside the repository.", 422)
        groups = self.changes(repo, requested_base)
        if normalized not in groups.paths_for(scope):
            raise GitError("That file is not in this set of changes.", 404)
        kind = classify_relative(normalized)
        if kind is not PathClass.VISIBLE:
            skipped = "generated" if kind is PathClass.GENERATED else "sensitive"
            return FileDiff(normalized, scope, False, False, skipped, None, [])
        if scope == "untracked":
            return self._untracked_diff(repo, normalized)
        args = ["diff", "--no-color", "--unified=3", *_diff_args()]
        if scope == "staged":
            args.insert(1, "--cached")
        elif scope == "committed":
            if groups.base is None:
                raise GitError("This repository has no local branch to compare.", 422)
            args.append(f"{groups.base}...HEAD")
        args.extend(["--", normalized])
        result = self._git(repo, args)
        if result.code != 0:
            raise GitError("Git could not read that diff.")
        lines, truncated, binary = _parse_unified(result.stdout)
        return FileDiff(
            normalized,
            scope,
            binary,
            truncated,
            None,
            None if binary else _language(normalized),
            [] if binary else lines,
        )

    def visible_paths(self, groups: ChangeGroups) -> set[str]:
        paths: set[str] = set()
        for group in (groups.staged, groups.unstaged, groups.committed, groups.untracked):
            paths.update(item.path for item in group if item.skipped is None)
        return paths

    def _untracked_diff(self, repo: Path, relative: str) -> FileDiff:
        target = _contained_file(repo, relative)
        if target is None:
            raise GitError("That file is not inside the repository.", 422)
        try:
            descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        except OSError as exc:
            raise GitError("That file could not be read.") from exc
        try:
            blob = os.read(descriptor, _DIFF_BYTES + 1)
        finally:
            os.close(descriptor)
        if b"\0" in blob:
            return FileDiff(relative, "untracked", True, False, None, None, [])
        truncated = len(blob) > _DIFF_BYTES
        text = blob[:_DIFF_BYTES].decode("utf-8", errors="replace")
        lines: list[DiffLine] = []
        for number, line in enumerate(text.splitlines(), start=1):
            if number > _DIFF_LINES:
                truncated = True
                break
            lines.append(DiffLine("add", line[:_LINE_CHARS], None, number))
        return FileDiff(relative, "untracked", False, truncated, None, _language(relative), lines)

    def _raw(self, repo: Path, args: list[str]) -> list[_RawChange]:
        result = self._git(repo, args)
        if result.code != 0:
            raise GitError("Git could not read the changes in this repository.")
        return _parse_raw(result.stdout)

    def _untracked(self, repo: Path) -> list[_RawChange]:
        result = self._git(repo, ["ls-files", "-z", "--others", "--exclude-standard"])
        if result.code != 0:
            raise GitError("Git could not read untracked files.")
        changes: list[_RawChange] = []
        for path in _split_paths(result.stdout):
            normalized = normalize_relative(path)
            if normalized is not None:
                changes.append(_RawChange("?", normalized))
        return changes

    def _branches(self, repo: Path) -> list[str]:
        result = self._git(repo, ["for-each-ref", "--format=%(refname:short)", "refs/heads"])
        if result.code != 0:
            raise GitError("Git could not list branches.")
        text = _decode(result.stdout)
        if text is None:
            raise GitError("Git could not list branches.")
        names = [name for name in text.splitlines() if safe_branch(name)]
        return sorted(set(names), key=str.casefold)

    def _branch(self, repo: Path) -> tuple[str | None, bool]:
        result = self._git(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
        if result.code != 0:
            raise GitError("Git could not read the current branch.")
        name = _decode(result.stdout.strip())
        if name is None:
            raise GitError("Git could not read the current branch.")
        if name == "HEAD":
            return None, True
        if not safe_branch(name):
            return None, False
        return name, False

    def _head(self, repo: Path) -> CommitInfo | None:
        if not self._has_head(repo):
            return None
        result = self._git(repo, ["log", "-1", "--format=%H%x00%s%x00%aI"])
        if result.code != 0:
            return None
        parts = result.stdout.split(b"\0", 2)
        if len(parts) < 2:
            return None
        sha = _decode(parts[0].strip())
        subject = _decode(parts[1])
        if sha is None or subject is None or len(sha) < 7:
            return None
        subject = redact_text(" ".join(subject.split()))[:200]
        committed_at = None
        if len(parts) == 3:
            stamp = _decode(parts[2].strip())
            if stamp is not None and "T" in stamp:
                committed_at = stamp
        return CommitInfo(sha, subject, committed_at)

    def _has_head(self, repo: Path) -> bool:
        result = self._git(repo, ["rev-parse", "--verify", "--quiet", "HEAD"])
        return result.code == 0 and len(result.stdout.strip()) >= 7

    def _dirty(self, repo: Path) -> bool:
        untracked = self._git(repo, ["ls-files", "-z", "--others", "--exclude-standard"])
        if untracked.code != 0:
            raise GitError("Git could not read the working tree status.")
        if not self._has_head(repo):
            return bool(untracked.stdout)
        staged = self._git(repo, ["diff", "--cached", "--quiet", *_diff_args()])
        unstaged = self._git(repo, ["diff", "--quiet", *_diff_args()])
        if staged.code not in {0, 1} or unstaged.code not in {0, 1}:
            raise GitError("Git could not read the working tree status.")
        return staged.code == 1 or unstaged.code == 1 or bool(untracked.stdout)

    def _require_git_dir(self, repo: Path) -> None:
        git_dir = repo / ".git"
        if git_dir.is_symlink() or not git_dir.is_dir():
            raise GitError("That folder is not a Git working tree.")

    def _git(self, repo: Path, args: list[str]) -> GitOutput:
        self.executions += 1
        try:
            return self._runner.run(repo, args)
        except CommandRejectedError as exc:
            raise GitError("Git inspection was refused.") from exc


def resolve_directory(raw_path: str) -> Path:
    if not raw_path.startswith("/") or "\x00" in raw_path or "\n" in raw_path:
        raise GitError("Repository path must be an absolute local path.", 422)
    try:
        resolved = Path(raw_path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise GitError("That path does not exist.") from exc
    if resolved.is_symlink() or not resolved.is_dir():
        raise GitError("That path is not a directory.")
    return resolved


def choose_base(requested: str | None, branches: list[str], current: str | None) -> str | None:
    if requested is not None:
        if requested not in branches or not safe_branch(requested):
            raise GitError("Choose a local branch from this repository.", 422)
        return requested
    for candidate in ("main", "master", current):
        if candidate is not None and candidate in branches:
            return candidate
    return branches[0] if branches else None


def safe_branch(name: str) -> bool:
    if ".." in name or "@{" in name or name.endswith((".lock", "/")):
        return False
    return _BRANCH.fullmatch(name) is not None


def _diff_args() -> list[str]:
    return ["--no-ext-diff", "--no-textconv"]


def _raw_diff_args() -> list[str]:
    return [*_diff_args(), "--raw", "-z"]


def _change_file(item: _RawChange) -> ChangeFile:
    kind = classify_relative(item.path)
    skipped = None
    if kind is PathClass.GENERATED:
        skipped = "generated"
    elif kind is not PathClass.VISIBLE:
        skipped = "sensitive"
    return ChangeFile(item.path, item.status, skipped)


def _cap(items: list[_RawChange]) -> tuple[list[_RawChange], bool]:
    if len(items) > _LIST_LIMIT:
        return items[:_LIST_LIMIT], True
    return items, False


def _parse_raw(raw: bytes) -> list[_RawChange]:
    if not raw:
        return []
    parts = raw.split(b"\0")
    if parts[-1] == b"":
        parts.pop()
    changes: list[_RawChange] = []
    index = 0
    while index < len(parts):
        header = _decode(parts[index])
        if header is None or not header.startswith(":"):
            raise GitError("Git returned a change list that could not be read.")
        status = header.split()[-1]
        index += 1
        if status[:1] in {"R", "C"}:
            if index + 1 >= len(parts):
                raise GitError("Git returned a change list that could not be read.")
            new_path = _decode(parts[index + 1])
            index += 2
        else:
            if index >= len(parts):
                raise GitError("Git returned a change list that could not be read.")
            new_path = _decode(parts[index])
            index += 1
        if new_path is None:
            continue
        normalized = normalize_relative(new_path)
        if normalized is None:
            continue
        changes.append(_RawChange(status[:1], normalized))
    return changes


def _split_paths(raw: bytes) -> list[str]:
    if not raw:
        return []
    parts = raw.split(b"\0")
    if parts[-1] == b"":
        parts.pop()
    found: list[str] = []
    for part in parts:
        text = _decode(part)
        if text:
            found.append(text)
    return found


def _parse_unified(raw: bytes) -> tuple[list[DiffLine], bool, bool]:
    if b"\0" in raw:
        return [], False, True
    truncated = False
    if len(raw) > _DIFF_BYTES:
        raw = raw[:_DIFF_BYTES]
        if b"\n" in raw:
            raw = raw.rsplit(b"\n", 1)[0]
        truncated = True
    text = raw.decode("utf-8", errors="replace")
    if text.startswith("Binary files ") or "\nBinary files " in text:
        return [], truncated, True
    lines: list[DiffLine] = []
    old_line: int | None = None
    new_line: int | None = None
    for raw_line in text.splitlines():
        if len(lines) >= _DIFF_LINES:
            truncated = True
            break
        hunk = _HUNK.match(raw_line)
        if hunk:
            old_line = int(hunk.group(1))
            new_line = int(hunk.group(2))
            lines.append(DiffLine("meta", raw_line[:_LINE_CHARS], None, None))
            continue
        if raw_line.startswith(
            (
                "diff --git ",
                "index ",
                "new file",
                "deleted file",
                "--- ",
                "+++ ",
                "old mode",
                "new mode",
                "similarity ",
                "rename ",
                "copy ",
            )
        ):
            lines.append(DiffLine("meta", raw_line[:_LINE_CHARS], None, None))
            continue
        if raw_line.startswith("\\"):
            lines.append(DiffLine("meta", raw_line[:_LINE_CHARS], None, None))
            continue
        if raw_line.startswith("+"):
            lines.append(DiffLine("add", raw_line[1:][:_LINE_CHARS], None, new_line))
            if new_line is not None:
                new_line += 1
            continue
        if raw_line.startswith("-"):
            lines.append(DiffLine("delete", raw_line[1:][:_LINE_CHARS], old_line, None))
            if old_line is not None:
                old_line += 1
            continue
        body = raw_line[1:] if raw_line.startswith(" ") else raw_line
        lines.append(DiffLine("context", body[:_LINE_CHARS], old_line, new_line))
        if old_line is not None:
            old_line += 1
        if new_line is not None:
            new_line += 1
    return lines, truncated, False


def _contained_file(repo: Path, relative: str) -> Path | None:
    current = repo
    for part in relative.split("/"):
        current = current / part
        try:
            if current.is_symlink():
                return None
        except OSError:
            return None
    try:
        if not current.is_file():
            return None
        current.resolve().relative_to(repo.resolve())
    except (OSError, ValueError):
        return None
    return current


def _language(relative: str) -> str | None:
    suffix = Path(relative).suffix.lower()
    return _LANGUAGES.get(suffix)


def _decode(raw: bytes) -> str | None:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
