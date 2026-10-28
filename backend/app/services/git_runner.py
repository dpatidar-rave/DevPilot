"""Read-only git execution. Arguments are a list. The shell is never used."""

from __future__ import annotations

import os
import select
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from app.services.command_policy import allowed_git_config, empty_hooks_dir, validate_git_argv

_STDOUT_LIMIT = 2_000_000
_STDERR_LIMIT = 4_096
_TIMEOUT_SECONDS = 20.0


class GitError(Exception):
    """A safe message for a git or path failure. It does not include file contents."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class GitOutput:
    code: int
    stdout: bytes
    stderr: bytes


class GitRunner:
    def __init__(self) -> None:
        self.executions = 0

    def run(self, repo: Path, args: list[str]) -> GitOutput:
        argv = _argv(repo, args)
        validate_git_argv(argv)
        empty_hooks_dir().mkdir(parents=True, exist_ok=True)
        self.executions += 1
        process = subprocess.Popen(
            argv,
            cwd=repo,
            env=_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        try:
            stdout, stderr, code = _capture(process)
        except GitError:
            raise
        except OSError as exc:
            raise GitError("Git could not be started on this machine.") from exc
        return GitOutput(code, stdout, stderr)


def _argv(repo: Path, args: list[str]) -> list[str]:
    work_tree = repo.as_posix()
    overrides: list[str] = []
    for value in sorted(allowed_git_config()):
        overrides.extend(["-c", value])
    return [
        "git",
        "--no-optional-locks",
        "--git-dir",
        f"{work_tree}/.git",
        "--work-tree",
        work_tree,
        *overrides,
        *args,
    ]


def _environment() -> dict[str, str]:
    path = os.environ.get("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin")
    return {
        "PATH": path,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
        "LC_ALL": "C",
    }


def _capture(process: subprocess.Popen[bytes]) -> tuple[bytes, bytes, int]:
    assert process.stdout is not None
    assert process.stderr is not None
    streams = [process.stdout, process.stderr]
    stdout = bytearray()
    stderr = bytearray()
    deadline = time.monotonic() + _TIMEOUT_SECONDS
    too_large = False
    while streams:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            process.kill()
            process.wait(timeout=2)
            raise GitError("Git took too long and was stopped.")
        readable, _, _ = select.select(streams, [], [], remaining)
        if not readable:
            if process.poll() is not None:
                break
            continue
        for stream in readable:
            chunk = os.read(stream.fileno(), 65536)
            if chunk == b"":
                streams.remove(stream)
                continue
            if stream is process.stdout:
                if len(stdout) + len(chunk) > _STDOUT_LIMIT:
                    too_large = True
                    process.kill()
                    streams.clear()
                    break
                stdout.extend(chunk)
            elif len(stderr) < _STDERR_LIMIT:
                stderr.extend(chunk[: _STDERR_LIMIT - len(stderr)])
    code = process.wait(timeout=2)
    if too_large:
        raise GitError("Git output was too large to show.")
    return bytes(stdout), bytes(stderr), code
