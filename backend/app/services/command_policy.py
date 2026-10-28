"""Command boundaries. Model output and repository text are never executed."""

from pathlib import Path


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
        "for-each-ref",
    }
)
_SHELL_TOKENS = (";", "|", "&", "`", "$(", "\x00")
_STATIC_CONFIG = frozenset(
    {
        "alias.status=",
        "alias.diff=",
        "alias.log=",
        "alias.rev-parse=",
        "alias.ls-files=",
        "alias.show=",
        "alias.for-each-ref=",
        "core.fsmonitor=",
        "core.untrackedCache=false",
        "diff.external=",
        "protocol.allow=never",
        "core.pager=cat",
    }
)


def empty_hooks_dir() -> Path:
    """Directory with no hook scripts. Git is pointed here so repo hooks do not run."""
    return Path(__file__).resolve().parent.parent / "empty_hooks"


def allowed_git_config() -> frozenset[str]:
    hooks = empty_hooks_dir().as_posix()
    return _STATIC_CONFIG | {f"core.hooksPath={hooks}"}


def validate_git_argv(argv: list[str]) -> list[str]:
    """Return a copy of a read-only git argv list, or reject it.

    This function does not execute the command. `git branch` is rejected because
    it can create a branch. Global options are limited to the flags the repository
    service builds itself.
    """
    if len(argv) < 2 or not _is_git_executable(argv[0]):
        raise CommandRejectedError("Only git inspection commands are allowed.")
    allowed_config = allowed_git_config()
    index = 1
    git_dir: str | None = None
    work_tree: str | None = None
    while index < len(argv):
        argument = argv[index]
        _reject_shell(argument, allow_newline=False)
        if argument == "--no-optional-locks":
            index += 1
            continue
        if argument in {"--git-dir", "--work-tree", "-C", "-c"}:
            if index + 1 >= len(argv):
                raise CommandRejectedError("A git option is missing its value.")
            value = argv[index + 1]
            _reject_shell(value, allow_newline=False)
            if argument == "--git-dir":
                git_dir = value
            elif argument == "--work-tree":
                work_tree = value
            elif argument == "-C" and not value:
                raise CommandRejectedError("git -C requires a repository path and a subcommand.")
            elif argument == "-c" and value not in allowed_config:
                raise CommandRejectedError("That git configuration override is not allowed.")
            index += 2
            continue
        if argument.startswith("-"):
            raise CommandRejectedError("Global git options are not allowed.")
        break
    if index >= len(argv):
        raise CommandRejectedError("A git subcommand is required.")
    if (git_dir is None) != (work_tree is None):
        raise CommandRejectedError("git-dir and work-tree must be set together.")
    if git_dir is not None and work_tree is not None:
        if not git_dir.startswith("/") or not work_tree.startswith("/"):
            raise CommandRejectedError("Repository paths must be absolute.")
        if git_dir != f"{work_tree.rstrip('/')}/.git":
            raise CommandRejectedError("git-dir must be the .git directory inside the work tree.")
    _reject_argument_tail(argv[index:])
    subcommand = argv[index]
    if subcommand in _MUTATING:
        raise CommandRejectedError(
            f"git {subcommand} is not allowed. "
            "DevPilot does not commit, push, merge, reset, clean, or switch branches."
        )
    if subcommand not in _READ_ONLY:
        raise CommandRejectedError(f"git {subcommand} is not a read-only inspection command.")
    return list(argv)


def _reject_argument_tail(args: list[str]) -> None:
    separator = False
    for argument in args:
        if argument == "--":
            separator = True
            continue
        _reject_shell(argument, allow_newline=separator)


def _is_git_executable(value: str) -> bool:
    if value == "git":
        return True
    if not value.startswith("/") or value.endswith("/"):
        return False
    return value.rsplit("/", 1)[-1] == "git"


def _reject_shell(argument: str, *, allow_newline: bool) -> None:
    if any(token in argument for token in _SHELL_TOKENS):
        raise CommandRejectedError("Command arguments must be plain data.")
    if not allow_newline and "\n" in argument:
        raise CommandRejectedError("Command arguments must be plain data.")


def refuse_untrusted_instructions(content: str) -> None:
    """Model responses and repository contents are data. Never execute them."""
    del content
    raise UntrustedContentError(
        "Repository contents and model responses are untrusted data. "
        "DevPilot will not execute commands, patches, or shell instructions from them."
    )
