"""Command boundaries. Model output and repository text are never executed."""


class CommandRejectedError(Exception):
    """The argv list is not a read-only git inspection."""


class UntrustedContentError(Exception):
    """Repository content or a model response was presented as an instruction."""


_MUTATING = frozenset(
    {
        "commit",
        "push",
        "merge",
        "reset",
        "clean",
        "switch",
        "checkout",
        "rebase",
        "pull",
        "fetch",
        "clone",
        "init",
        "add",
        "rm",
        "mv",
        "stash",
        "tag",
        "config",
        "apply",
        "am",
        "cherry-pick",
        "revert",
        "submodule",
        "gc",
        "filter-branch",
        "update-ref",
        "branch",
        "remote",
        "restore",
    }
)
_READ_ONLY = frozenset(
    {
        "status",
        "diff",
        "log",
        "show",
        "rev-parse",
        "ls-files",
        "blame",
        "describe",
        "shortlog",
        "version",
    }
)
_SHELL_TOKENS = (";", "|", "&", "`", "$(", "\n", "\x00")


def validate_git_argv(argv: list[str]) -> list[str]:
    """Return a copy of a read-only git argv list, or reject it.

    This function does not execute the command. `git branch` is rejected because
    it can create a branch. Global options other than `-C <path>` are rejected.
    """
    if len(argv) < 2 or argv[0] != "git":
        raise CommandRejectedError("Only git inspection commands are allowed.")
    for argument in argv:
        if any(token in argument for token in _SHELL_TOKENS):
            raise CommandRejectedError("Command arguments must be plain data.")
    index = 1
    if argv[1] == "-C":
        if len(argv) < 4 or not argv[2]:
            raise CommandRejectedError("git -C requires a repository path and a subcommand.")
        index = 3
    if argv[index].startswith("-"):
        raise CommandRejectedError("Global git options are not allowed.")
    subcommand = argv[index]
    if subcommand in _MUTATING:
        raise CommandRejectedError(
            f"git {subcommand} is not allowed. "
            "DevPilot does not commit, push, merge, reset, clean, or switch branches."
        )
    if subcommand not in _READ_ONLY:
        raise CommandRejectedError(f"git {subcommand} is not a read-only inspection command.")
    return list(argv)


def refuse_untrusted_instructions(content: str) -> None:
    """Model responses and repository contents are data. Never execute them."""
    del content
    raise UntrustedContentError(
        "Repository contents and model responses are untrusted data. "
        "DevPilot will not execute commands, patches, or shell instructions from them."
    )
