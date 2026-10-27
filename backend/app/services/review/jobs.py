"""Run one review at a time after an explicit user action."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

from app.services.model.errors import (
    InferenceBusy,
    InferenceCancelled,
    InferenceTimeout,
    LocalModelUnavailable,
    ModelMissingError,
    ModelPolicyError,
)
from app.services.model.inference import InferenceClient, ModelOptions
from app.services.model.policy import LARGE_MODEL_WARNING, assert_local_model_name, is_large_model
from app.services.persistence.service import NewFinding, NewReview, PersistenceService
from app.services.repository.service import DiffText, RepositoryPathError, RepositoryService
from app.services.review.engine import ReviewEngine, ReviewRun
from app.services.review.schema import ValidatedFinding


@dataclass
class ReviewJob:
    """In-memory status for a review. The diff and raw model text are not stored."""

    id: str
    repository_path: str
    status: str
    message: str
    findings: tuple[ValidatedFinding, ...] = ()
    errors: tuple[str, ...] = ()
    setup_instruction: Optional[str] = None
    retry: tuple[str, ...] = ()
    cancel_event: threading.Event = field(default_factory=threading.Event)


class ReviewJobManager:
    """Start, poll, and cancel local reviews."""

    def __init__(
        self,
        repository: RepositoryService,
        inference: InferenceClient,
        persistence: PersistenceService,
        options: ModelOptions,
    ) -> None:
        self._repository = repository
        self._engine = ReviewEngine(inference)
        self._persistence = persistence
        self._options = options
        self._jobs: dict[str, ReviewJob] = {}
        self._guard = threading.Lock()
        self._active_id: Optional[str] = None

    @property
    def options(self) -> ModelOptions:
        return self._options

    def start(self, path: str, *, approved: bool, confirm_large_model: bool) -> ReviewJob:
        """Read a diff and, when there is something to review, call the local model."""
        assert_local_model_name(self._options.model)
        if is_large_model(self._options.model) and confirm_large_model is not True:
            raise ModelPolicyError(LARGE_MODEL_WARNING)
        captured = self._repository.diff_against_head(path, approved=approved)
        with self._guard:
            if self._active_id is not None:
                raise InferenceBusy("A local review is already running. Cancel it before starting another.")
            job = ReviewJob(id=str(uuid.uuid4()), repository_path=path, status="running", message="Running.")
            self._jobs[job.id] = job
            self._active_id = job.id
        worker = threading.Thread(
            target=self._execute,
            args=(job, captured),
            name="devpilot-review",
            daemon=True,
        )
        worker.start()
        return job

    def get(self, job_id: str) -> ReviewJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def cancel(self, job_id: str) -> ReviewJob:
        job = self.get(job_id)
        job.cancel_event.set()
        return job

    def _execute(self, job: ReviewJob, captured: DiffText) -> None:
        try:
            run = self._engine.review_diff(captured.text, self._options, job.cancel_event)
            if captured.truncated:
                run = ReviewRun(
                    findings=run.findings,
                    errors=run.errors + ("The diff was truncated before it was sent to the model.",),
                    contacted_model=run.contacted_model,
                    cancelled=run.cancelled,
                    truncated=True,
                )
            if job.cancel_event.is_set() or run.cancelled:
                self._finish(job, "cancelled", run, "The review was cancelled.")
                return
            self._finish(job, "completed", run, _summary(run))
        except ModelMissingError as exc:
            job.status = "failed"
            job.message = exc.setup_instruction
            job.setup_instruction = exc.setup_instruction
            self._persist(job)
        except LocalModelUnavailable as exc:
            job.status = "failed"
            job.message = str(exc)
            job.retry = exc.retry
            self._persist(job)
        except (InferenceTimeout, InferenceCancelled, ModelPolicyError) as exc:
            job.status = "cancelled" if isinstance(exc, InferenceCancelled) else "failed"
            job.message = str(exc)
            self._persist(job)
        except RepositoryPathError as exc:
            job.status = "failed"
            job.message = str(exc)
            self._persist(job)
        except Exception:
            job.status = "failed"
            job.message = "The local review failed before it could finish."
            self._persist(job)
        finally:
            with self._guard:
                if self._active_id == job.id:
                    self._active_id = None

    def _finish(self, job: ReviewJob, status: str, run: ReviewRun, message: str) -> None:
        job.status = status
        job.message = message
        job.findings = run.findings
        job.errors = run.errors
        self._persist(job)

    def _persist(self, job: ReviewJob) -> None:
        try:
            if not self._persistence.database_ready():
                return
            self._persistence.save_review(
                NewReview(
                    repository_path=job.repository_path,
                    status=job.status,
                    summary=job.message,
                ),
                tuple(
                    NewFinding(
                        path=item.path,
                        line_start=item.line_start,
                        line_end=item.line_end,
                        severity=item.severity,
                        category=item.category,
                        summary=item.summary,
                        confidence=item.confidence,
                        uncertain=item.uncertain,
                    )
                    for item in job.findings
                ),
            )
        except Exception:
            return


def _summary(run: ReviewRun) -> str:
    confirmed = sum(1 for item in run.findings if not item.uncertain)
    uncertain = sum(1 for item in run.findings if item.uncertain)
    if not run.contacted_model and not run.findings:
        extra = f" {run.errors[0]}" if run.errors else ""
        return f"No local changes were sent to the model.{extra}"
    return (
        f"{confirmed} reported findings and {uncertain} uncertain findings. "
        "Uncertain findings are not treated as defects."
    )
