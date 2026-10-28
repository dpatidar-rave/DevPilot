"""Run one allowlisted quality command. shell=True is never used."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO

from app.services.quality_policy import (
    MissingToolError,
    QualityCommandError,
    assert_invocation,
    safe_path,
)

OUTPUT_LIMIT = 65_536
_MAX_TIMEOUT = 600.0
_POPEN = subprocess.Popen


@dataclass(frozen=True)
class Execution:
    argv: tuple[str, ...]
    working_directory: str
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    exit_code: int | None
    stdout: str
    stderr: str
    truncated: bool
    timed_out: bool


class QualityRunner:
    """Counts real process starts. A rejected command does not increment the count."""

    def __init__(self) -> None:
        self.executions = 0

    def execute(
        self,
        argv: list[str],
        cwd: Path,
        timeout: float,
        output_limit: int = OUTPUT_LIMIT,
        root: Path | None = None,
    ) -> Execution:
        if root is None:
            raise QualityCommandError("The working directory must be the registered repository.")
        assert_invocation(root, cwd, argv)
        self.executions += 1
        return run_process(argv, cwd, timeout, output_limit)


def run_process(argv: list[str], cwd: Path, timeout: float, output_limit: int) -> Execution:
    """Start a process from an argument list. Callers enforce the allowlist first."""
    if timeout <= 0 or timeout > _MAX_TIMEOUT:
        raise QualityCommandError("The time limit is not allowlisted.")
    if output_limit <= 0 or output_limit > OUTPUT_LIMIT:
        raise QualityCommandError("The output limit is not allowlisted.")
    started_at = datetime.now(UTC)
    clock = time.monotonic()
    try:
        process = _POPEN(
            argv,
            cwd=cwd,
            env=_child_environment(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise MissingToolError(
            "The interpreter could not be started, so the command was not run."
        ) from exc
    except OSError as exc:
        raise QualityCommandError("The command could not be started.") from exc
    stdout, stderr, truncated, timed_out = _collect(process, timeout, output_limit)
    finished_at = datetime.now(UTC)
    duration_ms = max(0, int((time.monotonic() - clock) * 1000))
    exit_code = None if timed_out else process.returncode
    return Execution(
        argv=tuple(argv),
        working_directory=cwd.resolve().as_posix(),
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        truncated=truncated,
        timed_out=timed_out,
    )


def _collect(
    process: subprocess.Popen[bytes],
    timeout: float,
    output_limit: int,
) -> tuple[str, str, bool, bool]:
    stdout_box: list[tuple[bytes, bool]] = []
    stderr_box: list[tuple[bytes, bool]] = []
    out_thread = threading.Thread(
        target=_capture,
        args=(process.stdout, output_limit, stdout_box),
        daemon=True,
    )
    err_thread = threading.Thread(
        target=_capture,
        args=(process.stderr, output_limit, stderr_box),
        daemon=True,
    )
    out_thread.start()
    err_thread.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate(process)
    finally:
        if process.poll() is None:
            _terminate(process)
        out_thread.join(timeout=5)
        err_thread.join(timeout=5)
    stdout, stdout_truncated = stdout_box[0] if stdout_box else (b"", False)
    stderr, stderr_truncated = stderr_box[0] if stderr_box else (b"", False)
    return (
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
        stdout_truncated or stderr_truncated,
        timed_out,
    )


def _capture(
    stream: IO[bytes] | None,
    limit: int,
    box: list[tuple[bytes, bool]],
) -> None:
    box.append(_read_limited(stream, limit))


def _read_limited(stream: IO[bytes] | None, limit: int) -> tuple[bytes, bool]:
    if stream is None:
        return b"", False
    chunks: list[bytes] = []
    total = 0
    truncated = False
    while True:
        piece = stream.read(8192)
        if not piece:
            break
        if total >= limit:
            truncated = True
            continue
        room = limit - total
        if len(piece) > room:
            chunks.append(piece[:room])
            total = limit
            truncated = True
        else:
            chunks.append(piece)
            total += len(piece)
    return b"".join(chunks), truncated


def _terminate(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.kill()
        except (ProcessLookupError, OSError):
            return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _child_environment(cwd: Path) -> dict[str, str]:
    return {
        "PATH": safe_path(cwd),
        "HOME": os.environ.get("HOME", "/tmp"),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TERM": "dumb",
    }
