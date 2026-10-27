"""Review engine. It calls an inference protocol and never executes model text."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.services.model.errors import InferenceCancelled
from app.services.model.inference import InferenceClient, InferenceRequest, ModelOptions
from app.services.review.chunks import ChunkSet, DiffChunk, chunk_unified_diff, diff_char_budget
from app.services.review.schema import ValidatedFinding, validate_model_output
from app.services.review.service import ReviewService


@dataclass(frozen=True)
class ReviewRun:
    """Validated findings only. Raw model text is not retained."""

    findings: tuple[ValidatedFinding, ...]
    errors: tuple[str, ...]
    contacted_model: bool
    cancelled: bool
    truncated: bool


class ReviewEngine:
    """Turn a unified diff into schema-checked findings."""

    def __init__(self, inference: InferenceClient) -> None:
        self._inference = inference
        self._boundary = ReviewService()

    def review_diff(
        self,
        diff: str,
        options: ModelOptions,
        cancel_event: threading.Event,
    ) -> ReviewRun:
        """Review `diff`. An empty diff does not contact the model."""
        packed: ChunkSet = chunk_unified_diff(
            diff,
            max_chars=diff_char_budget(options.context_length, options.max_output_tokens),
        )
        if not packed.chunks:
            return ReviewRun((), packed.notes, False, False, packed.truncated)
        self._inference.prepare(options)
        findings: list[ValidatedFinding] = []
        errors = list(packed.notes)
        for chunk in packed.chunks:
            if cancel_event.is_set():
                return ReviewRun(tuple(findings), tuple(errors), True, True, packed.truncated)
            try:
                raw = self._inference.complete(
                    InferenceRequest(prompt=_prompt(chunk), options=options),
                    cancel_event,
                )
            except InferenceCancelled:
                return ReviewRun(tuple(findings), tuple(errors), True, True, packed.truncated)
            self._boundary.accept_model_output(raw)
            validated = validate_model_output(raw, chunk)
            findings.extend(validated.findings)
            errors.extend(validated.errors)
        return ReviewRun(tuple(findings), tuple(errors), True, False, packed.truncated)


def _prompt(chunk: DiffChunk) -> str:
    ranges = ", ".join(f"{item.start}-{item.end}" for item in chunk.ranges) or "none"
    return (
        "Review the unified diff below. Return one JSON object and nothing else. "
        'Schema: {"findings":[{"path":"string","line_start":1,"line_end":1,'
        '"severity":"low|medium|high|critical","category":"short-slug",'
        '"summary":"string","confidence":"low|medium|high"}]}. '
        "Use confidence low when you are unsure. Do not include shell commands. "
        f"File: {chunk.path}. Changed line numbers: {ranges}.\n"
        f"{chunk.text}"
    )
