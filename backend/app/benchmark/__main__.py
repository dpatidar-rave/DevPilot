"""Run the local model benchmark. This command does not download a model."""

from __future__ import annotations

import json
import threading
import time

from app.benchmark.score import BenchmarkReport, CaseOutcome, finding_matches, score
from app.benchmark import load_cases
from app.config import get_settings
from app.services.model.errors import LocalModelUnavailable, ModelMissingError, ModelPolicyError
from app.services.model.inference import ModelOptions
from app.services.model.ollama import OllamaClient
from app.services.model.ollama_inference import OllamaInference
from app.services.model.policy import KEEP_ALIVE, is_large_model
from app.services.review.engine import ReviewEngine


def main() -> int:
    """Evaluate the configured local model and print metrics only."""
    settings = get_settings()
    options = ModelOptions(
        model=settings.model_name,
        context_length=settings.context_length,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        timeout_seconds=settings.ollama_timeout_seconds,
        keep_alive=KEEP_ALIVE,
        endpoint=settings.ollama_base_url,
        large_model=is_large_model(settings.model_name),
    )
    if options.large_model:
        print(
            "Refusing to benchmark a 20B or larger model unless DEVPILOT_CONFIRM_LARGE_MODEL=1. "
            "The default model is qwen2.5-coder:7b."
        )
        import os

        if os.environ.get("DEVPILOT_CONFIRM_LARGE_MODEL") != "1":
            return 2
    inference = OllamaInference(OllamaClient(settings.ollama_base_url))
    try:
        inference.prepare(options)
    except (ModelMissingError, LocalModelUnavailable, ModelPolicyError) as exc:
        print(str(exc))
        return 2
    cases = load_cases()
    engine = ReviewEngine(inference)
    outcomes: list[CaseOutcome] = []
    for case in cases:
        started = time.perf_counter()
        try:
            run = engine.review_diff(case.diff, options, threading.Event())
            confirmed = [item for item in run.findings if not item.uncertain]
            uncertain = [item for item in run.findings if item.uncertain]
            matched = case.kind == "defect" and any(
                item.path == case.path and finding_matches(item.category, item.summary, case.match_terms)
                for item in confirmed
            )
            error = None
            if run.errors and not run.findings:
                error = "The model response could not be validated."
            outcomes.append(
                CaseOutcome(
                    case_id=case.case_id,
                    kind=case.kind,
                    matched=matched,
                    confirmed=len(confirmed),
                    uncertain=len(uncertain),
                    error=error,
                    elapsed_seconds=round(time.perf_counter() - started, 3),
                )
            )
        except (LocalModelUnavailable, ModelMissingError, ModelPolicyError) as exc:
            outcomes.append(
                CaseOutcome(
                    case.case_id,
                    case.kind,
                    False,
                    0,
                    0,
                    str(exc),
                    round(time.perf_counter() - started, 3),
                )
            )
        except Exception:
            outcomes.append(
                CaseOutcome(
                    case.case_id,
                    case.kind,
                    False,
                    0,
                    0,
                    "The local review failed before it could finish.",
                    round(time.perf_counter() - started, 3),
                )
            )
    report = score(options.model, cases, tuple(outcomes))
    print(_render(report))
    return 0


def _render(report: BenchmarkReport) -> str:
    payload = {
        "model": report.model,
        "detection_rate": report.detection_rate,
        "false_positive_rate": report.false_positive_rate,
        "response_time_seconds": report.response_time_seconds,
        "errors": list(report.errors),
        "cases": [
            {
                "id": item.case_id,
                "kind": item.kind,
                "matched": item.matched,
                "confirmed": item.confirmed,
                "uncertain": item.uncertain,
                "error": item.error,
                "elapsed_seconds": item.elapsed_seconds,
            }
            for item in report.cases
        ],
    }
    return json.dumps(payload, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
