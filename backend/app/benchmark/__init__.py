"""Load the local benchmark fixture."""

from __future__ import annotations

import json
from pathlib import Path

from app.benchmark.score import BenchmarkCase

_FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "benchmark" / "cases.json"


def load_cases(path: Path = _FIXTURE) -> tuple[BenchmarkCase, ...]:
    """Read the fixture from disk. The diffs stay in memory for the run only."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("Benchmark fixture is missing cases.")
    cases: list[BenchmarkCase] = []
    for item in raw_cases:
        if not isinstance(item, dict):
            raise ValueError("Benchmark fixture contains an invalid case.")
        kind = item.get("kind")
        if kind not in {"defect", "harmless"}:
            raise ValueError("Benchmark case kind must be defect or harmless.")
        terms = item.get("match_terms", [])
        if not isinstance(terms, list) or any(not isinstance(term, str) for term in terms):
            raise ValueError("Benchmark match terms must be strings.")
        cases.append(
            BenchmarkCase(
                case_id=str(item["id"]),
                kind=str(kind),
                path=str(item["path"]),
                diff=str(item["diff"]),
                match_terms=tuple(str(term) for term in terms),
            )
        )
    return tuple(cases)
