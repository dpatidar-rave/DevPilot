"""Split a unified diff into bounded chunks that keep path, ranges, and context."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_DIFF_GIT = re.compile(r"^diff --git a/(.+) b/(.+)$")
_MAX_CHUNKS = 20
_CONTEXT_LINES = 3


@dataclass(frozen=True)
class LineRange:
    """Inclusive changed-line span reported with a chunk."""

    start: int
    end: int


@dataclass(frozen=True)
class DiffChunk:
    """One model input. `text` is untrusted repository data."""

    path: str
    ranges: tuple[LineRange, ...]
    changed_lines: frozenset[int]
    text: str


@dataclass(frozen=True)
class ChunkSet:
    """Chunks plus notes that are safe to show. Notes do not include file bodies."""

    chunks: tuple[DiffChunk, ...]
    notes: tuple[str, ...]
    truncated: bool


@dataclass
class _Line:
    kind: str
    text: str
    old_line: int
    new_line: int


def diff_char_budget(context_length: int, max_output_tokens: int) -> int:
    """Leave room for the instruction and the reserved output inside the context."""
    available_tokens = context_length - max_output_tokens - 700
    if available_tokens < 200:
        available_tokens = 200
    return available_tokens * 4


def chunk_unified_diff(diff: str, *, max_chars: int) -> ChunkSet:
    """Parse `diff` and pack it into chunks no larger than `max_chars`."""
    if max_chars < 200:
        max_chars = 200
    files = _parse_files(diff)
    chunks: list[DiffChunk] = []
    notes: list[str] = []
    truncated = False
    for path, hunks, binary in files:
        if binary:
            notes.append(f"Binary file {path} was not sent to the model.")
            continue
        for hunk_lines in hunks:
            pieces = _split_hunk(path, hunk_lines, max_chars)
            for piece in pieces:
                if len(chunks) >= _MAX_CHUNKS:
                    truncated = True
                    notes.append(
                        "The diff was longer than 20 chunks. Later changes were not sent to the model."
                    )
                    return ChunkSet(tuple(chunks), tuple(notes), True)
                chunks.append(piece)
    return ChunkSet(tuple(chunks), tuple(notes), truncated)


def _parse_files(diff: str) -> list[tuple[str, list[list[_Line]], bool]]:
    files: list[tuple[str, list[list[_Line]], bool]] = []
    current_path = ""
    current_hunks: list[list[_Line]] = []
    current_lines: list[_Line] | None = None
    binary = False
    old_line = 0
    new_line = 0

    def finish() -> None:
        nonlocal current_lines
        if current_lines is not None:
            current_hunks.append(current_lines)
            current_lines = None
        if current_path:
            files.append((current_path, current_hunks, binary))

    for raw in diff.splitlines():
        if raw.startswith("diff --git "):
            finish()
            current_hunks = []
            current_lines = None
            binary = False
            current_path = _path_from_header(raw)
            continue
        if raw.startswith("Binary files ") or raw.startswith("GIT binary patch"):
            binary = True
            continue
        if raw.startswith("+++ "):
            renamed = _path_from_plus(raw)
            if renamed:
                current_path = renamed
            continue
        if raw.startswith("--- ") or raw.startswith("index ") or raw.startswith("new file") or raw.startswith("deleted file"):
            continue
        match = _HUNK.match(raw)
        if match:
            if current_lines is not None:
                current_hunks.append(current_lines)
            old_line = int(match.group(1))
            new_line = int(match.group(3))
            current_lines = []
            continue
        if current_lines is None or raw.startswith("\\"):
            continue
        if raw.startswith("+"):
            current_lines.append(_Line("+", raw, old_line, new_line))
            new_line += 1
        elif raw.startswith("-"):
            current_lines.append(_Line("-", raw, old_line, new_line))
            old_line += 1
        else:
            text = raw if raw.startswith(" ") else f" {raw}"
            current_lines.append(_Line(" ", text, old_line, new_line))
            old_line += 1
            new_line += 1
    finish()
    return files


def _split_hunk(path: str, lines: list[_Line], max_chars: int) -> list[DiffChunk]:
    if not lines:
        return []
    if len(_render(path, lines).text) <= max_chars:
        return [_render(path, lines)]
    pieces: list[DiffChunk] = []
    start = 0
    while start < len(lines):
        end = start + 1
        while end < len(lines):
            candidate = _with_context(lines, start, end + 1)
            if len(_render(path, candidate).text) > max_chars:
                break
            end += 1
        rendered = _render(path, _with_context(lines, start, end))
        if rendered.changed_lines:
            pieces.append(rendered)
        start = end if end > start else start + 1
    return pieces


def _with_context(lines: list[_Line], start: int, end: int) -> list[_Line]:
    context_start = start
    seen = 0
    index = start - 1
    while index >= 0 and seen < _CONTEXT_LINES:
        if lines[index].kind == " ":
            context_start = index
            seen += 1
        index -= 1
    context_end = end
    seen = 0
    index = end
    while index < len(lines) and seen < _CONTEXT_LINES:
        if lines[index].kind == " ":
            context_end = index + 1
            seen += 1
        index += 1
    return lines[context_start:context_end]


def _render(path: str, lines: list[_Line]) -> DiffChunk:
    changed: set[int] = set()
    ranges: list[LineRange] = []
    span_start: int | None = None
    span_end: int | None = None
    for line in lines:
        number = line.new_line if line.kind == "+" else line.old_line if line.kind == "-" else None
        if number is None:
            if span_start is not None and span_end is not None:
                ranges.append(LineRange(span_start, span_end))
                span_start = None
                span_end = None
            continue
        changed.add(number)
        if span_start is None:
            span_start = number
        span_end = number
    if span_start is not None and span_end is not None:
        ranges.append(LineRange(span_start, span_end))
    first = lines[0]
    old_count = sum(1 for line in lines if line.kind != "+")
    new_count = sum(1 for line in lines if line.kind != "-")
    header = (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -{first.old_line},{max(old_count, 0)} +{first.new_line},{max(new_count, 0)} @@\n"
    )
    body = "\n".join(line.text for line in lines)
    return DiffChunk(path=path, ranges=tuple(ranges), changed_lines=frozenset(changed), text=header + body + "\n")


def _path_from_header(raw: str) -> str:
    match = _DIFF_GIT.match(raw)
    if match is None:
        return "unknown"
    return match.group(2)


def _path_from_plus(raw: str) -> str:
    name = raw[4:].strip()
    if name.startswith("b/"):
        return name[2:]
    if name == "/dev/null":
        return ""
    return name
