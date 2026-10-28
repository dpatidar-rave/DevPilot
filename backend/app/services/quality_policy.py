"""Allowlisted quality-check commands.

The model never supplies these argument lists. A saved command is checked again
immediately before a process starts. The shell is not involved.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path

TOOLS = ("phpcs", "phpstan", "phpunit", "composer", "magento")

LABELS = {
    "phpcs": "PHP_CodeSniffer",
    "phpstan": "PHPStan",
    "phpunit": "PHPUnit",
    "composer": "Composer validation",
    "magento": "Magento project check",
}

TIMEOUTS = {
    "phpcs": 180.0,
    "phpstan": 180.0,
    "phpunit": 180.0,
    "composer": 60.0,
    "magento": 120.0,
}

WARNING = (
    "Approved project scripts can still have side effects. PHPUnit and the Magento CLI "
    "can write files or bootstrap the application. DevPilot does not install Composer "
    "packages, change project configuration, or run deployment commands, and it runs a "
    "command only after you confirm it."
)

_SCRIPTS = {
    "vendor/bin/phpcs": "phpcs",
    "vendor/bin/phpstan": "phpstan",
    "vendor/bin/phpunit": "phpunit",
    "bin/magento": "magento",
}

_CONFIG_FILES = {
    "phpcs": ("phpcs.xml", "phpcs.xml.dist", ".phpcs.xml"),
    "phpstan": ("phpstan.neon", "phpstan.neon.dist", "phpstan.dist.neon"),
    "phpunit": ("phpunit.xml", "phpunit.xml.dist"),
    "composer": ("composer.json",),
    "magento": ("bin/magento", "app/etc/di.xml"),
}

_SUGGESTED = {
    "phpcs": ("php", "vendor/bin/phpcs"),
    "phpstan": (
        "php",
        "vendor/bin/phpstan",
        "analyse",
        "--no-progress",
        "--memory-limit=1G",
    ),
    "phpunit": ("php", "vendor/bin/phpunit", "--do-not-cache-result"),
    "composer": ("composer", "validate", "--no-check-publish", "--no-check-all"),
    "magento": ("php", "bin/magento", "--version"),
}

_MAX_ARGS = 24
_MAX_ARG_LENGTH = 240
_SHELL_CHARACTERS = frozenset(";|&`$<>\n\r\x00()\"'\\")
_PHP_NAME = re.compile(r"^php(-?\d+(\.\d+)*)?(\.exe)?$")
_COMPOSER_NAME = re.compile(r"^composer(\.phar)?$")
_LONG_FLAG = re.compile(r"^--[a-zA-Z0-9][a-zA-Z0-9-]{0,40}$")
_SHORT_FLAG = re.compile(r"^-[A-Za-z]{1,8}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,200}$")
_MEMORY = re.compile(r"^--memory-limit=\d{1,5}[KMG]$")
_DENIED_SHORT = frozenset("rRdaBEFfilmw")
_DENIED_LONG = frozenset(
    {
        "--define",
        "--ini",
        "--run",
        "--rf",
        "--ri",
        "--re",
        "--rc",
        "--working-dir",
        "--global",
        "--generate-baseline",
        "--generate-configuration",
        "--migrate-configuration",
        "--fix",
        "--clear-result-cache",
    }
)
_DESTRUCTIVE = frozenset(
    {
        "install",
        "update",
        "require",
        "remove",
        "create-project",
        "config",
        "run-script",
        "exec",
        "dump-autoload",
        "phpcbf",
        "clear-result-cache",
        "setup:upgrade",
        "setup:install",
        "setup:di:compile",
        "setup:static-content:deploy",
        "setup:uninstall",
        "setup:db-schema:upgrade",
        "setup:db-data:upgrade",
        "setup:backup",
        "setup:rollback",
        "deploy:mode:set",
        "maintenance:enable",
        "maintenance:disable",
        "cache:flush",
        "cache:clean",
        "cache:enable",
        "cache:disable",
        "indexer:reindex",
        "indexer:reset",
        "module:enable",
        "module:disable",
        "config:set",
        "config:sensitive:set",
        "config:show",
        "app:config:import",
        "app:config:dump",
        "sampledata:deploy",
        "sampledata:remove",
        "admin:user:create",
        "admin:user:unlock",
    }
)
_COMPOSER_COMMANDS = frozenset({"validate", "check-platform-reqs"})
_COMPOSER_FLAGS = frozenset(
    {
        "--no-check-publish",
        "--no-check-all",
        "--strict",
        "--no-check-version",
        "--no-check-lock",
        "--no-ansi",
        "--ansi",
        "--no-interaction",
        "-n",
        "--quiet",
        "-q",
        "--format=json",
        "--format=text",
        "--no-dev",
        "--lock",
    }
)
_MAGENTO_ACTIONS = frozenset({"--version", "-V", "module:status"})
_MAGENTO_FLAGS = frozenset({"--no-ansi", "--ansi", "--verbose", "-v"})
_PHPSTAN_MODES = frozenset({"analyse", "analyze", "list", "--version"})
_DESTRUCTIVE_MESSAGE = (
    "That command can change the project or deploy it, so DevPilot will not run it."
)
_EXECUTABLE_MESSAGE = "That executable is not allowlisted."
_ARGUMENT_MESSAGE = "A command argument is not allowlisted."
_PATH_MESSAGE = "A path argument must stay inside the repository."


class QualityCommandError(Exception):
    """The argument list was rejected before a process could start."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class MissingToolError(Exception):
    """The interpreter or project tool is not available. Nothing was started."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class DetectedTool:
    tool: str
    label: str
    available: bool
    files: tuple[str, ...]
    suggested_argv: tuple[str, ...]
    reason: str | None


def display_command(argv: list[str]) -> str:
    """A human-readable command. It is never passed back to a shell."""
    return " ".join(shlex.quote(part) for part in argv)


def safe_path(repo: Path | None = None) -> str:
    """PATH with the current directory and the repository removed."""
    root = repo.resolve() if repo is not None else None
    kept: list[str] = []
    for item in os.environ.get("PATH", "").split(os.pathsep):
        if item in {"", "."}:
            continue
        try:
            resolved = Path(item).resolve()
        except OSError:
            continue
        if root is not None and (resolved == root or _is_inside(resolved, root)):
            continue
        kept.append(item)
    if kept:
        return os.pathsep.join(kept)
    return "/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin"


def validate_command(repo: Path, argv: list[str]) -> str:
    """Return the tool id. Reject shell text, destructive commands, and outside paths."""
    if not argv or len(argv) > _MAX_ARGS:
        raise QualityCommandError("The command length is not allowlisted.")
    for arg in argv:
        if not isinstance(arg, str) or len(arg) > _MAX_ARG_LENGTH:
            raise QualityCommandError("A command argument is empty or too long.")
        _reject_shell(arg)
        _reject_destructive(arg)
    if argv[0] == "composer":
        _validate_composer(argv[1:])
        return "composer"
    script, rest = _php_script(argv)
    tool = _SCRIPTS.get(script)
    if tool is None:
        raise QualityCommandError(_EXECUTABLE_MESSAGE)
    if tool == "magento":
        _validate_magento(rest)
    elif tool == "phpstan":
        _validate_phpstan(repo, rest)
    else:
        _validate_php_tool(repo, rest)
    return tool


def resolve_invocation(repo: Path, argv: list[str]) -> list[str]:
    """Turn a saved command into the exact argv a process may receive."""
    tool = validate_command(repo, argv)
    if tool == "composer":
        interpreter = require_interpreter(repo, "composer")
        return [str(interpreter), *argv[1:]]
    script, rest = _php_script(argv)
    status = _script_status(repo, script)
    if status == "outside":
        raise QualityCommandError("The project tool must stay inside the repository.")
    if status != "ok":
        raise MissingToolError(
            "The project tool was not found in this repository, so the command was not run."
        )
    interpreter = require_interpreter(repo, "php")
    return [str(interpreter), script, *rest]


def assert_invocation(repo: Path, cwd: Path, argv: list[str]) -> None:
    """Last check before a process is created. Absolute interpreters stay off the repo."""
    root = repo.resolve()
    try:
        current = cwd.resolve()
    except OSError as exc:
        raise QualityCommandError(
            "The working directory must be the registered repository."
        ) from exc
    if current != root:
        raise QualityCommandError("The working directory must be the registered repository.")
    if not argv:
        raise QualityCommandError(_EXECUTABLE_MESSAGE)
    interpreter = Path(argv[0])
    if not interpreter.is_absolute():
        raise QualityCommandError(_EXECUTABLE_MESSAGE)
    try:
        resolved_interpreter = interpreter.resolve()
    except OSError as exc:
        raise QualityCommandError(_EXECUTABLE_MESSAGE) from exc
    if resolved_interpreter == root or _is_inside(resolved_interpreter, root):
        raise QualityCommandError(_EXECUTABLE_MESSAGE)
    name = resolved_interpreter.name
    if _COMPOSER_NAME.fullmatch(name):
        validate_command(repo, ["composer", *argv[1:]])
        return
    if not _PHP_NAME.fullmatch(name):
        raise QualityCommandError(_EXECUTABLE_MESSAGE)
    if len(argv) < 2 or argv[1] not in _SCRIPTS:
        raise QualityCommandError(_EXECUTABLE_MESSAGE)
    if _script_status(repo, argv[1]) != "ok":
        raise QualityCommandError("The project tool must stay inside the repository.")
    validate_command(repo, ["php", *argv[1:]])


def detect_tools(repo: Path) -> list[DetectedTool]:
    """Report config files and binaries. This does not start a process."""
    root = repo.resolve()
    php_ready = _interpreter_available(root, "php")
    composer_ready = _interpreter_available(root, "composer")
    detected: list[DetectedTool] = []
    for tool in TOOLS:
        files = tuple(relative for relative in _CONFIG_FILES[tool] if _inside_file(root, relative))
        if tool == "composer":
            available = composer_ready and "composer.json" in files
            reason = _composer_reason(composer_ready, "composer.json" in files)
        elif tool == "magento":
            binary = _script_status(root, "bin/magento")
            available = php_ready and binary == "ok" and "app/etc/di.xml" in files
            reason = _php_tool_reason(php_ready, binary, "app/etc/di.xml" in files)
        else:
            binary = _script_status(root, f"vendor/bin/{tool}")
            available = php_ready and binary == "ok"
            reason = _php_tool_reason(php_ready, binary, bool(files))
        suggested = _SUGGESTED[tool] if available else ()
        detected.append(
            DetectedTool(
                tool=tool,
                label=LABELS[tool],
                available=available,
                files=files,
                suggested_argv=suggested,
                reason=None if available else reason,
            )
        )
    return detected


def require_interpreter(repo: Path, name: str) -> Path:
    """Resolve php or composer from PATH, never from the repository."""
    if name not in {"php", "composer"}:
        raise QualityCommandError(_EXECUTABLE_MESSAGE)
    found = shutil.which(name, path=safe_path(repo))
    if found is None:
        raise MissingToolError(_missing_interpreter(name))
    try:
        resolved = Path(found).resolve()
    except OSError as exc:
        raise MissingToolError(_missing_interpreter(name)) from exc
    pattern = _PHP_NAME if name == "php" else _COMPOSER_NAME
    if not pattern.fullmatch(resolved.name) or not resolved.is_file():
        raise QualityCommandError(_EXECUTABLE_MESSAGE)
    root = repo.resolve()
    if resolved == root or _is_inside(resolved, root):
        raise QualityCommandError(_EXECUTABLE_MESSAGE)
    return resolved


def _interpreter_available(repo: Path, name: str) -> bool:
    try:
        require_interpreter(repo, name)
    except (MissingToolError, QualityCommandError):
        return False
    return True


def _missing_interpreter(name: str) -> str:
    tool = "PHP" if name == "php" else "Composer"
    return f"{tool} was not found on PATH, so the command was not run."


def _php_script(argv: list[str]) -> tuple[str, list[str]]:
    if argv[0] == "php":
        if len(argv) < 2 or argv[1].startswith("-"):
            raise QualityCommandError(_EXECUTABLE_MESSAGE)
        return argv[1], argv[2:]
    if argv[0] in _SCRIPTS:
        return argv[0], argv[1:]
    raise QualityCommandError(_EXECUTABLE_MESSAGE)


def _validate_composer(args: list[str]) -> None:
    if not args or args[0] not in _COMPOSER_COMMANDS:
        raise QualityCommandError("That Composer command is not allowlisted.")
    if args[0] == "validate" and not {"--no-check-publish", "--no-check-all"} <= set(args[1:]):
        raise QualityCommandError(
            "Composer validate must include --no-check-publish and --no-check-all."
        )
    for arg in args[1:]:
        if arg not in _COMPOSER_FLAGS:
            raise QualityCommandError(_ARGUMENT_MESSAGE)


def _validate_magento(args: list[str]) -> None:
    if not args or not any(arg in _MAGENTO_ACTIONS for arg in args):
        raise QualityCommandError("Magento commands must be --version or module:status.")
    for arg in args:
        if arg not in _MAGENTO_ACTIONS and arg not in _MAGENTO_FLAGS:
            raise QualityCommandError("That Magento command is not allowlisted.")


def _validate_phpstan(repo: Path, args: list[str]) -> None:
    if not any(arg in _PHPSTAN_MODES for arg in args):
        raise QualityCommandError("PHPStan commands must include analyse, list, or --version.")
    for arg in args:
        if arg in _PHPSTAN_MODES:
            continue
        _validate_php_argument(repo, arg)


def _validate_php_tool(repo: Path, args: list[str]) -> None:
    for arg in args:
        _validate_php_argument(repo, arg)


def _validate_php_argument(repo: Path, arg: str) -> None:
    if arg.startswith("--memory-limit="):
        if not _MEMORY.fullmatch(arg):
            raise QualityCommandError("The memory limit is not allowlisted.")
        return
    if arg.startswith("--"):
        name, separator, value = arg.partition("=")
        if name in _DENIED_LONG or not _LONG_FLAG.fullmatch(name):
            raise QualityCommandError(_ARGUMENT_MESSAGE)
        if separator and _looks_like_path(value):
            _require_inside(repo, value)
        return
    if _SHORT_FLAG.fullmatch(arg):
        if any(character in _DENIED_SHORT for character in arg[1:]):
            raise QualityCommandError(_ARGUMENT_MESSAGE)
        return
    if _looks_like_path(arg):
        _require_inside(repo, arg)
        return
    if _TOKEN.fullmatch(arg):
        return
    raise QualityCommandError(_ARGUMENT_MESSAGE)


def _reject_shell(arg: str) -> None:
    if any(character in arg for character in _SHELL_CHARACTERS):
        raise QualityCommandError("A command argument contains a shell character.")


def _reject_destructive(arg: str) -> None:
    if arg in _DESTRUCTIVE or Path(arg).name in {"phpcbf", "bash", "sh", "zsh", "rm"}:
        raise QualityCommandError(_DESTRUCTIVE_MESSAGE)


def _looks_like_path(value: str) -> bool:
    return (
        value.startswith(("/", ".", "~"))
        or "\\" in value
        or "/" in value
        or ".." in Path(value).parts
    )


def _require_inside(repo: Path, raw: str) -> None:
    if raw.startswith("~") or "\x00" in raw:
        raise QualityCommandError(_PATH_MESSAGE)
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise QualityCommandError(_PATH_MESSAGE)
    try:
        resolved = (repo / candidate).resolve()
    except OSError as exc:
        raise QualityCommandError(_PATH_MESSAGE) from exc
    if not _is_inside(resolved, repo.resolve()):
        raise QualityCommandError(_PATH_MESSAGE)


def _script_status(repo: Path, relative: str) -> str:
    if relative not in _SCRIPTS:
        return "missing"
    return _file_status(repo, relative)


def _inside_file(repo: Path, relative: str) -> bool:
    if ".." in Path(relative).parts or Path(relative).is_absolute():
        return False
    return _file_status(repo, relative) == "ok"


def _file_status(repo: Path, relative: str) -> str:
    path = repo / relative
    try:
        if path.is_symlink():
            target = path.resolve(strict=True)
            if target.is_file() and _is_inside(target, repo.resolve()):
                return "ok"
            return "outside"
        if path.is_file():
            return "ok"
    except OSError:
        return "outside"
    return "missing"


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _composer_reason(interpreter: bool, config: bool) -> str:
    if not interpreter:
        return "Composer was not found on PATH."
    if not config:
        return "composer.json was not found in this repository."
    return "Composer validation is not available for this repository."


def _php_tool_reason(interpreter: bool, binary: str, config: bool) -> str:
    if binary == "outside":
        return "The project tool points outside the repository, so DevPilot will not run it."
    if not interpreter:
        return "PHP was not found on PATH."
    if binary != "ok":
        if config:
            return "A configuration file is present, and the tool itself was not found."
        return "This repository does not include that tool."
    return "This check is not available for this repository."
