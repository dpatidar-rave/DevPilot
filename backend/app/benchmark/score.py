"""Score a local benchmark without retaining prompts or model text."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    kind: str
    path: str
    diff: str
    match_terms: tuple[str, ...]


@dataclass(frozen=True)
class CaseOutcome:
    case_id: str
    kind: str
    matched: bool
    confirmed: int
    uncertain: int
    error: str | None
    elapsed_seconds: float


@dataclass(frozen=True)
class BenchmarkReport:
    model: str
    detection_rate: float
    false_positive_rate: float
    response_time_seconds: float
    errors: tuple[str, ...]
    cases: tuple[CaseOutcome, ...]


def score(model: str, cases: tuple[BenchmarkCase, ...], outcomes: tuple[CaseOutcome, ...]) -> BenchmarkReport:
    """Compute rates from recorded outcomes. Missing cases are errors, not successes."""
    by_id = {item.case_id: item for item in outcomes}
    ordered: list[CaseOutcome] = []
    errors: list[str] = []
    for case in cases:
        outcome = by_id.get(case.case_id)
        if outcome is None:
            outcome = CaseOutcome(case.case_id, case.kind, False, 0, 0, "No outcome was recorded.", 0.0)
        ordered.append(outcome)
        if outcome.error:
            errors.append(f"{outcome.case_id}: {outcome.error}")
    defects = [item for item in ordered if item.kind == "defect"]
    harmless = [item for item in ordered if item.kind == "harmless"]
    detected = sum(1 for item in defects if item.matched and item.error is None)
    false_positives = sum(1 for item in harmless if item.confirmed > 0 and item.error is None)
    return BenchmarkReport(
        model=model,
        detection_rate=_rate(detected, len(defects)),
        false_positive_rate=_rate(false_positives, len(harmless)),
        response_time_seconds=round(sum(item.elapsed_seconds for item in ordered), 3),
        errors=tuple(errors),
        cases=tuple(ordered),
    )


def finding_matches(category: str, summary: str, terms: tuple[str, ...]) -> bool:
    """Return whether a confirmed finding mentions an expected defect."""
    haystack = _normalize(category) + _normalize(summary)
    return any(_normalize(term) in haystack for term in terms if _normalize(term))


def _normalize(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 3)
