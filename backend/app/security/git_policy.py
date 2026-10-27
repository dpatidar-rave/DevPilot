"""Exact allowlist for read-only git inspection."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence, Tuple

from app.security.command_gate import CommandRejected

EMPTY_HOOKS_DIR = Path(__file__).resolve().parent / "empty_hooks"

ALLOWED_GIT_ARGV: Tuple[Tuple[str, ...], ...] = (
    ("git", "rev-parse", "--is-inside-work-tree"),
    ("git", "symbolic-ref", "--short", "HEAD"),
    ("git", "status", "--porcelain=v1", "--branch"),
    ("git", "diff", "--no-ext-diff", "--no-textconv", "HEAD"),
)


def build_safe_git_argv(logical_argv: Sequence[str]) -> list[str]:
    """Turn an allowlisted logical git command into a hardened argument list.

    Repository config is untrusted. Aliases, fsmonitor, hooks, and external
    diff programs can execute shell commands, so every invocation overrides them.
    """
    parts = tuple(logical_argv)
    if parts not in ALLOWED_GIT_ARGV:
        raise CommandRejected(
            "That git command is not allowlisted. Commit, push, merge, reset, "
            "clean, and branch switching are blocked."
        )
    subcommand = parts[1]
    hooks = str(EMPTY_HOOKS_DIR)
    return [
        "git",
        "--no-pager",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=",
        "-c",
        "core.sshCommand=",
        "-c",
        f"core.hooksPath={hooks}",
        "-c",
        "diff.external=",
        "-c",
        "credential.helper=",
        "-c",
        "protocol.allow=never",
        "-c",
        f"alias.{subcommand}=",
        *parts[1:],
    ]
