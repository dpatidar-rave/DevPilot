"""Run a local review. The model cannot change the repository or call tools."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.config import Settings
from app.logging_config import log_event
from app.models.review import Review, ReviewFinding
from app.schemas.review import FindingResponse, ReviewDetail, ReviewRecord, SkippedFile
from app.services.git_runner import GitError
from app.services.model_gateway import CancellationToken, InferenceClient, InferenceError
from app.services.persistence import SessionFactory, get_project
from app.services.repository import RepositoryService
from app.services.review_analysis import (
    GroundedFinding,
    PreparedReview,
    chunk_budget,
    collect_materials,
    dedupe_findings,
    interpret_response,
    system_prompt,
    user_prompt,
)

Collector = Callable[[Path, str, list[str], int], PreparedReview]

ERROR_MESSAGES = {
    "timeout": (
        "The local model timed out. Retry the review. "
        "DevPilot will not switch to a hosted model."
    ),
    "model_missing": (
        "The configured Ollama model is not available on this machine. "
        "Pull it yourself. DevPilot does not download models and will not use a hosted model."
    ),
    "unavailable": (
        "Ollama is not reachable at the configured loopback address. "
        "Start it locally and retry. DevPilot will not use a remote model."
    ),
    "busy": "The local model is already running a review. Wait for it to finish, then retry.",
    "interrupted": "The review stopped because DevPilot restarted. Start it again.",
    "internal": "The review stopped because of a local error. Check the local log and retry.",
}
_FATAL = frozenset({"timeout", "model_missing", "unavailable", "busy"})


class ReviewRejected(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class ReviewService:
    def __init__(
        self,
        inference: InferenceClient,
        sessions: SessionFactory,
        settings: Settings | None = None,
        repositories: RepositoryService | None = None,
        *,
        synchronous: bool = False,
        collector: Collector | None = None,
    ) -> None:
        self._inference = inference
        self._sessions = sessions
        self._settings = settings
        self._repositories = repositories or RepositoryService()
        self._synchronous = synchronous
        self._collector = collector
        self._tokens: dict[str, CancellationToken] = {}
        self._lock = threading.Lock()

    @property
    def inference(self) -> InferenceClient:
        return self._inference

    @property
    def sessions(self) -> SessionFactory:
        return self._sessions

    def start(self, project_id: str, base_ref: str, paths: list[str]) -> str:
        if self._settings is None or self._settings.model_name.strip() == "":
            raise ReviewRejected(422, "Configure a local Ollama model before starting a review.")
        project = get_project(self._sessions, project_id)
        if project is None:
            raise ReviewRejected(404, "That repository is not registered.")
        if self._is_running(project_id):
            raise ReviewRejected(409, "A review is already running for this repository.")
        budget = chunk_budget(self._settings.context_length, self._settings.max_output_tokens)
        try:
            prepared = self._prepare(Path(project.path), base_ref, paths, budget)
        except GitError as exc:
            raise ReviewRejected(exc.status_code, exc.message) from exc
        review_id = str(uuid4())
        now = datetime.now(UTC)
        summary = _summary(prepared, self._settings.model_name)
        with self._sessions() as session:
            session.add(
                Review(
                    id=review_id,
                    project_id=project_id,
                    status="running",
                    base_ref=prepared.base,
                    head_ref=prepared.head,
                    model_name=self._settings.model_name,
                    context_length=self._settings.context_length,
                    temperature=self._settings.temperature,
                    max_output_tokens=self._settings.max_output_tokens,
                    timeout_seconds=self._settings.timeout_seconds,
                    keep_alive=self._settings.keep_alive,
                    created_at=now,
                    started_at=now,
                    finding_count=0,
                    files_reviewed=len(prepared.reviewed),
                    files_skipped=len(prepared.skipped),
                    chunks_total=len(prepared.chunks),
                    chunks_completed=0,
                    summary=summary,
                    limitations_json=json.dumps(prepared.limitations),
                    skipped_json=json.dumps(
                        [{"path": path, "reason": reason} for path, reason in prepared.skipped]
                    ),
                    reviewed_json=json.dumps(prepared.reviewed),
                )
            )
            session.commit()
        log_event(
            logging.INFO,
            "review_started",
            review_id=review_id,
            model=self._settings.model_name,
            chunks=len(prepared.chunks),
        )
        token = CancellationToken()
        with self._lock:
            self._tokens[review_id] = token
        if self._synchronous:
            self._execute(review_id, prepared, token)
        else:
            threading.Thread(
                target=self._execute,
                args=(review_id, prepared, token),
                name=f"devpilot-review-{review_id[:8]}",
                daemon=True,
            ).start()
        return review_id

    def cancel(self, review_id: str) -> None:
        review = self._load(review_id)
        if review is None:
            raise ReviewRejected(404, "That review is not stored.")
        if review.status != "running":
            raise ReviewRejected(409, "That review is not running.")
        with self._lock:
            token = self._tokens.get(review_id)
        if token is None:
            self._finish(review_id, "cancelled", error_code=None, findings=[], done=None)
            return
        token.cancel()

    def list_records(self) -> list[ReviewRecord]:
        with self._sessions() as session:
            rows = list(session.scalars(select(Review).order_by(Review.created_at.desc())))
            return [_record(row) for row in rows]

    def detail(self, review_id: str) -> ReviewDetail:
        with self._sessions() as session:
            review = session.get(Review, review_id)
            if review is None:
                raise ReviewRejected(404, "That review is not stored.")
            findings = list(
                session.scalars(
                    select(ReviewFinding)
                    .where(ReviewFinding.review_id == review_id)
                    .order_by(ReviewFinding.file_path, ReviewFinding.start_line)
                )
            )
            return ReviewDetail(
                **_record(review).model_dump(),
                findings=[_finding_response(item) for item in findings],
            )

    def _prepare(self, repo: Path, base: str, paths: list[str], budget: int) -> PreparedReview:
        if self._collector is not None:
            return self._collector(repo, base, paths, budget)
        checked = self._repositories.ensure_registered(repo.as_posix())
        return collect_materials(
            self._repositories,
            checked,
            base,
            paths,
            budget=budget,
        )

    def _execute(self, review_id: str, prepared: PreparedReview, token: CancellationToken) -> None:
        findings: list[GroundedFinding] = []
        limitations = list(prepared.limitations)
        if not prepared.chunks:
            limitations.append("The selection has no reviewable diff text.")
        status = "completed"
        error_code: str | None = None
        done = 0
        try:
            if prepared.chunks:
                for index, chunk in enumerate(prepared.chunks, start=1):
                    if token.is_cancelled():
                        status = "cancelled"
                        break
                    try:
                        raw = self._inference.complete(
                            [
                                {"role": "system", "content": system_prompt()},
                                {
                                    "role": "user",
                                    "content": user_prompt(
                                        chunk,
                                        base=prepared.base,
                                        head=prepared.head,
                                    ),
                                },
                            ],
                            token,
                        )
                    except InferenceError as exc:
                        if exc.code == "cancelled" or token.is_cancelled():
                            status = "cancelled"
                            break
                        if exc.code in _FATAL:
                            status = "failed"
                            error_code = exc.code
                            limitations.append(ERROR_MESSAGES.get(exc.code, "The review stopped."))
                            break
                        limitations.append("The model response for one chunk could not be read.")
                        done = index
                        self._progress(review_id, done)
                        continue
                    if token.is_cancelled():
                        status = "cancelled"
                        break
                    accepted, notes = interpret_response(raw, chunk)
                    findings.extend(accepted)
                    limitations.extend(notes)
                    done = index
                    self._progress(review_id, done)
            findings = dedupe_findings(findings)
        except Exception:
            log_event(logging.ERROR, "review_failed", review_id=review_id, error_type="internal")
            status = "failed"
            error_code = "internal"
        finally:
            with self._lock:
                self._tokens.pop(review_id, None)
        self._finish(
            review_id,
            status,
            error_code=error_code,
            findings=findings,
            limitations=limitations,
            done=done,
        )
        log_event(
            logging.INFO,
            "review_finished",
            review_id=review_id,
            status=status,
            finding_count=len(findings),
        )

    def _progress(self, review_id: str, done: int) -> None:
        with self._sessions() as session:
            review = session.get(Review, review_id)
            if review is None or review.status != "running":
                return
            review.chunks_completed = done
            session.commit()

    def _finish(
        self,
        review_id: str,
        status: str,
        *,
        error_code: str | None,
        findings: list[GroundedFinding],
        limitations: list[str] | None = None,
        done: int | None,
    ) -> None:
        now = datetime.now(UTC)
        with self._sessions() as session:
            review = session.get(Review, review_id)
            if review is None or review.status not in {"running", "pending"}:
                return
            review.status = status
            review.error_code = error_code
            review.finished_at = now
            review.finding_count = len(findings)
            if done is not None:
                review.chunks_completed = done
            if limitations is not None:
                review.limitations_json = json.dumps(_unique(limitations)[:30])
            if status == "completed" and not findings:
                review.summary = (
                    f"{review.summary} The model did not report a grounded finding."
                ).strip()
            session.add_all(_finding_rows(review_id, findings, now))
            session.commit()

    def _is_running(self, project_id: str) -> bool:
        with self._sessions() as session:
            statement = select(Review.id).where(
                Review.project_id == project_id,
                Review.status == "running",
            )
            return session.scalar(statement) is not None

    def _load(self, review_id: str) -> Review | None:
        with self._sessions() as session:
            review = session.get(Review, review_id)
            if review is not None:
                session.expunge(review)
            return review


def mark_interrupted(sessions: SessionFactory) -> None:
    """A review cannot still be running after the process starts."""
    with sessions() as session:
        rows = list(session.scalars(select(Review).where(Review.status == "running")))
        now = datetime.now(UTC)
        for review in rows:
            review.status = "failed"
            review.error_code = "interrupted"
            review.finished_at = now
        if rows:
            session.commit()


def _summary(prepared: PreparedReview, model: str) -> str:
    return (
        f"Local review with {model}. "
        f"Compared with {prepared.base or 'the selected branch'} at {prepared.head or 'HEAD'}. "
        f"{len(prepared.reviewed)} file(s) were sent to the model and "
        f"{len(prepared.skipped)} file(s) were skipped. "
        "Findings are AI suggestions, not deterministic test results, and are not guaranteed."
    )


def _record(review: Review) -> ReviewRecord:
    return ReviewRecord(
        id=review.id,
        project_id=review.project_id,
        status=_status(review.status),
        base_ref=review.base_ref,
        head_ref=review.head_ref,
        model=review.model_name,
        context_length=review.context_length,
        created_at=review.created_at,
        started_at=review.started_at,
        finished_at=review.finished_at,
        error_code=review.error_code,
        error_message=ERROR_MESSAGES.get(review.error_code or "", None),
        finding_count=review.finding_count,
        summary=review.summary or "",
        limitations=_strings(review.limitations_json),
        skipped_files=_skipped(review.skipped_json),
        reviewed_files=_strings(review.reviewed_json),
        files_reviewed=review.files_reviewed or 0,
        files_skipped=review.files_skipped or 0,
        chunks_total=review.chunks_total or 0,
        chunks_completed=review.chunks_completed or 0,
        temperature=review.temperature,
        max_output_tokens=review.max_output_tokens,
        timeout_seconds=review.timeout_seconds,
        keep_alive=review.keep_alive,
    )


def _finding_rows(
    review_id: str,
    findings: list[GroundedFinding],
    created_at: datetime,
) -> list[ReviewFinding]:
    return [
        ReviewFinding(
            id=str(uuid4()),
            review_id=review_id,
            file_path=item.file_path,
            scope=item.scope,
            start_line=item.start_line,
            end_line=item.end_line,
            severity=item.severity,
            category=item.category,
            title=item.title,
            summary=item.explanation,
            evidence=item.evidence,
            remediation=item.remediation,
            confidence=item.confidence,
            uncertain=item.uncertain,
            validation_status="uncertain",
            verification="grounded",
            stable_key=item.stable_key,
            created_at=created_at,
        )
        for item in findings
    ]


def _finding_response(item: ReviewFinding) -> FindingResponse:
    return FindingResponse(
        id=item.id,
        stable_key=item.stable_key or item.id,
        file_path=item.file_path,
        scope=item.scope or "",
        start_line=item.start_line,
        end_line=item.end_line,
        severity=_severity(item.severity),
        category=item.category,
        title=item.title,
        explanation=item.summary,
        evidence=item.evidence or "",
        remediation=item.remediation or "",
        confidence=item.confidence,
        uncertain=item.uncertain,
        evidence_checked=item.verification == "grounded",
    )


def _status(value: str) -> str:
    if value in {"pending", "running", "completed", "failed", "cancelled"}:
        return value
    return "failed"


def _severity(value: str) -> str:
    if value in {"critical", "high", "medium", "low", "info"}:
        return value
    return "info"


def _strings(raw: str | None) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


def _skipped(raw: str | None) -> list[SkippedFile]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    items: list[SkippedFile] = []
    for item in parsed:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            reason = item.get("reason")
            items.append(
                SkippedFile(path=item["path"], reason=reason if isinstance(reason, str) else "")
            )
    return items


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result
