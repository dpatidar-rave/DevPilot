"""Approval gate for any process DevPilot might start."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class CommandOrigin(Enum):
    """Who asked for a command. Only an explicit user action may proceed."""

    USER = "user"
    MODEL = "model"
    REPOSITORY = "repository"


class CommandRejected(Exception):
    """A command was refused before any process was started."""


@dataclass(frozen=True)
class CommandRequest:
    """A command that has not run yet."""

    argv: Tuple[str, ...]
    approved: bool
    origin: CommandOrigin


def authorize(request: CommandRequest) -> None:
    """Reject model output, repository text, and unapproved commands."""
    if request.origin is not CommandOrigin.USER:
        raise CommandRejected(
            "Commands from the model, repository contents, or documentation are never executed."
        )
    if request.approved is not True:
        raise CommandRejected("Command execution requires an explicit user-approved action.")
    if not request.argv:
        raise CommandRejected("Command arguments must be a non-empty list of strings.")
    for part in request.argv:
        if not isinstance(part, str) or part == "":
            raise CommandRejected("Command arguments must be a non-empty list of strings.")
        if "\x00" in part or "\n" in part or "\r" in part:
            raise CommandRejected("Command arguments contain unsupported characters.")
