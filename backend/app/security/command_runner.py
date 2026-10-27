"""The only module allowed to start a process."""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.security.command_gate import CommandRejected, CommandRequest, authorize
from app.security.git_policy import build_safe_git_argv

_TIMEOUT_SECONDS = 15
logger = logging.getLogger("devpilot.commands")


@dataclass(frozen=True)
class CommandResult:
    """Captured output. Callers must treat both streams as untrusted text."""

    exit_code: int
    stdout: str
    stderr: str


def scrubbed_env() -> dict[str, str]:
    """Pass a minimal environment so git cannot inherit external command hooks."""
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "LANG": "C",
        "LC_ALL": "C",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
    }


class CommandRunner:
    """Run an approved, allowlisted git inspection."""

    def run(self, request: CommandRequest, cwd: Path) -> CommandResult:
        authorize(request)
        resolved = cwd.resolve()
        if not resolved.is_dir():
            raise CommandRejected("Working directory does not exist.")
        argv = build_safe_git_argv(request.argv)
        try:
            completed = subprocess.run(
                argv,
                cwd=str(resolved),
                shell=False,
                capture_output=True,
                text=True,
                check=False,
                stdin=subprocess.DEVNULL,
                timeout=_TIMEOUT_SECONDS,
                env=scrubbed_env(),
            )
        except FileNotFoundError as exc:
            logger.error("Git executable was not found.")
            raise CommandRejected(
                "Git is not installed or not on PATH. Install Git locally and retry."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            logger.error("Git inspection timed out.")
            raise CommandRejected(
                "Git inspection timed out. Nothing else was executed."
            ) from exc
        return CommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
