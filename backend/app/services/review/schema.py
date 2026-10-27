"""Strict parsing of model review JSON. Invalid output becomes an error, not a finding."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.review.chunks import DiffChunk


class FindingDraft(BaseModel):
    """One finding object from the model. Extra fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    line_start: int = Field(ge=1, le=1_000_000)
    line_end: int = Field(ge=1, le=1_000_000)
    severity: Literal["low", "medium", "high", "critical"]
    category: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=400)
    confidence: Literal["low", "medium", "high"]


class _Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[object]


@dataclass(frozen=True)
class ValidatedFinding:
    """A schema-valid finding. `uncertain` means it is not a confirmed defect."""

    path: str
    line_start: int
    line_end: int
    severity: str
    category: str
    summary: str
    confidence: str
    uncertain: bool


@dataclass(frozen=True)
class ValidatedChunk:
    findings: tuple[ValidatedFinding, ...]
    errors: tuple[str, ...]


_SCHEMA_ERROR = "A model response did not match the review schema and was discarded."
_FINDING_ERROR = "A finding was dropped because it did not match the review schema."


def validate_model_output(raw: str, chunk: DiffChunk) -> ValidatedChunk:
    """Parse model text. The raw response is not returned or logged."""
    payload = _extract_object(raw)
    if payload is None:
        return ValidatedChunk((), (_SCHEMA_ERROR,))
    try:
        envelope = _Envelope.model_validate(payload)
    except ValidationError:
        return ValidatedChunk((), (_SCHEMA_ERROR,))
    findings: list[ValidatedFinding] = []
    errors: list[str] = []
    for item in envelope.findings:
        if not isinstance(item, dict):
            errors.append(_FINDING_ERROR)
            continue
        try:
            draft = FindingDraft.model_validate(item)
        except ValidationError:
            errors.append(_FINDING_ERROR)
            continue
        if draft.line_end < draft.line_start:
            errors.append(_FINDING_ERROR)
            continue
        reasons: list[str] = []
        if draft.confidence == "low":
            reasons.append("low")
        if draft.path != chunk.path:
            reasons.append("path")
        if not _overlaps(draft.line_start, draft.line_end, chunk.changed_lines):
            reasons.append("lines")
        findings.append(
            ValidatedFinding(
                path=draft.path,
                line_start=draft.line_start,
                line_end=draft.line_end,
                severity=draft.severity,
                category=draft.category,
                summary=draft.summary,
                confidence=draft.confidence,
                uncertain=bool(reasons),
            )
        )
    return ValidatedChunk(tuple(findings), tuple(errors))


def _overlaps(start: int, end: int, changed: frozenset[int]) -> bool:
    return any(start <= number <= end for number in changed)


def _extract_object(raw: str) -> dict[str, object] | None:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    value = _loads(text)
    if value is None:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        value = _loads(text[start : end + 1])
    if not isinstance(value, dict):
        return None
    return value


def _loads(text: str) -> object | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
