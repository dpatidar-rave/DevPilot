"""Build and store a release assessment. This service does not call a model or run a command."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.logging_config import log_event
from app.models.quality import QualityCheckRun
from app.models.release import FindingDecision, ReleaseChecklistDecision, ReleaseReport
from app.models.review import Review, ReviewFinding
from app.schemas.release import (
    ChecklistDecisionWrite,
    FindingDecisionWrite,
    ReleaseAssessment,
    ReleaseReportDetail,
    ReleaseReportRecord,
)
from app.services.git_runner import GitError
from app.services.persistence import SessionFactory, get_project, list_release_reports
from app.services.release_assessment import (
    CHECKLIST_KEYS,
    Assessment,
    AssessmentInput,
    ChecklistInput,
    DecisionInput,
    FindingInput,
    ModelInput,
    QualityInput,
    build_assessment,
    dump_json,
    render_markdown,
    serialize,
)
from app.services.repository import RepositoryService

_QUALITY_TOOLS = ("phpcs", "phpstan", "phpunit", "composer", "magento")
_QUALITY_RESULTS = frozenset({"pass", "fail", "skipped", "timed_out"})
_READINESS_NOTE = {
    "blocked": "Blocked",
    "needs_review": "Needs review",
    "ready_for_human_approval": "Ready for human approval",
}


class ReleaseRejected(Exception):
    """A safe message for a rejected release action. It does not include source."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ReleaseReportService:
    def __init__(self, sessions: SessionFactory, repositories: RepositoryService) -> None:
        self._sessions = sessions
        self._repositories = repositories

    def list_records(self) -> list[ReleaseReportRecord]:
        return [
            ReleaseReportRecord.model_validate(row, from_attributes=True)
            for row in list_release_reports(self._sessions)
        ]

    def preview(self, project_id: str, review_id: str) -> ReleaseAssessment:
        return ReleaseAssessment.model_validate(serialize(self._assess(project_id, review_id)))

    def save_finding_decision(
        self,
        review_id: str,
        finding_id: str,
        body: FindingDecisionWrite,
    ) -> ReleaseAssessment:
        reason, reviewer = _decision_text(body)
        now = datetime.now(UTC)
        with self._sessions() as session:
            finding = session.get(ReviewFinding, finding_id)
            review = session.get(Review, review_id)
            if review is None or finding is None or finding.review_id != review.id:
                raise ReleaseRejected(404, "That finding is not part of this review.")
            if body.decision == "waived" or (
                body.decision == "dismissed" and finding.severity == "critical"
            ):
                reason, reviewer = _require_identity(reason, reviewer, "This decision")
            current = session.get(FindingDecision, finding_id)
            if current is None:
                session.add(
                    FindingDecision(
                        finding_id=finding_id,
                        decision=body.decision,
                        reason=reason,
                        reviewer_label=reviewer,
                        updated_at=now,
                    )
                )
            else:
                current.decision = body.decision
                current.reason = reason
                current.reviewer_label = reviewer
                current.updated_at = now
            project_id = review.project_id
            session.commit()
        return self.preview(project_id, review_id)

    def save_checklist_decision(
        self,
        review_id: str,
        item_key: str,
        body: ChecklistDecisionWrite,
    ) -> ReleaseAssessment:
        if item_key not in CHECKLIST_KEYS:
            raise ReleaseRejected(422, "That checklist item is not part of the release report.")
        if item_key == "critical_high" and body.status != "pending":
            raise ReleaseRejected(
                422,
                "Record a decision on each critical or high finding.",
            )
        reason = _plain(body.reason, 500, "Reason")
        reviewer = _plain(body.reviewer, 80, "Reviewer")
        if body.status in {"waived", "not_applicable", "passed"}:
            reason, reviewer = _require_identity(reason, reviewer, "This checklist decision")
        now = datetime.now(UTC)
        with self._sessions() as session:
            review = session.get(Review, review_id)
            if review is None:
                raise ReleaseRejected(404, "That review is not stored.")
            current = session.get(ReleaseChecklistDecision, (review_id, item_key))
            if current is None:
                session.add(
                    ReleaseChecklistDecision(
                        review_id=review_id,
                        item_key=item_key,
                        project_id=review.project_id,
                        status=body.status,
                        reason=reason,
                        reviewer_label=reviewer,
                        updated_at=now,
                    )
                )
            else:
                current.status = body.status
                current.reason = reason
                current.reviewer_label = reviewer
                current.updated_at = now
            project_id = review.project_id
            session.commit()
        return self.preview(project_id, review_id)

    def generate(self, project_id: str, review_id: str) -> ReleaseReportDetail:
        assessment = self._assess(project_id, review_id)
        report_id = str(uuid4())
        payload = dump_json(assessment)
        markdown = render_markdown(assessment)
        now = assessment.generated_at
        with self._sessions() as session:
            session.add(
                ReleaseReport(
                    id=report_id,
                    project_id=project_id,
                    review_id=review_id,
                    title=f"Release readiness — {assessment.project_name}"[:200],
                    status="draft",
                    note=_READINESS_NOTE[assessment.readiness],
                    created_at=now,
                    readiness=assessment.readiness,
                    base_ref=assessment.base_ref[:200],
                    head_sha=assessment.head_sha[:64],
                    repository_head_sha=assessment.repository_head_sha[:64],
                    generated_at=now,
                    model_name=assessment.model.name[:128],
                    report_json=payload,
                    report_markdown=markdown,
                )
            )
            session.commit()
        log_event(
            logging.INFO,
            "release_report_saved",
            project_id=project_id,
            review_id=review_id,
            report_id=report_id,
            readiness=assessment.readiness,
        )
        return self.read(report_id)

    def read(self, report_id: str) -> ReleaseReportDetail:
        row = self._row(report_id)
        if row.report_json is None or row.status not in {"draft", "ready", "archived"}:
            raise ReleaseRejected(404, "That release report is not stored.")
        try:
            payload = json.loads(row.report_json)
        except json.JSONDecodeError as exc:
            raise ReleaseRejected(404, "That release report is not stored.") from exc
        assessment = ReleaseAssessment.model_validate(payload)
        return ReleaseReportDetail(
            id=row.id,
            title=row.title,
            status=row.status,
            **assessment.model_dump(),
        )

    def markdown(self, report_id: str) -> str:
        row = self._row(report_id)
        if row.report_markdown is None:
            raise ReleaseRejected(404, "That release report is not stored.")
        return row.report_markdown

    def json_export(self, report_id: str) -> str:
        row = self._row(report_id)
        if row.report_json is None:
            raise ReleaseRejected(404, "That release report is not stored.")
        return row.report_json

    def _assess(self, project_id: str, review_id: str) -> Assessment:
        project = get_project(self._sessions, project_id)
        if project is None:
            raise ReleaseRejected(404, "That repository is not registered.")
        data = self._inputs(project.id, project.name, review_id)
        try:
            repo = self._repositories.ensure_registered(project.path)
            inspection = self._repositories.inspect(repo)
        except GitError as exc:
            raise ReleaseRejected(exc.status_code, exc.message) from exc
        head = inspection.head.sha if inspection.head is not None else ""
        stamped = AssessmentInput(
            project_id=data.project_id,
            project_name=data.project_name,
            review_id=data.review_id,
            review_status=data.review_status,
            base_ref=data.base_ref,
            head_sha=data.head_sha,
            repository_head_sha=head,
            dirty=inspection.dirty,
            generated_at=data.generated_at,
            model=data.model,
            findings=data.findings,
            decisions=data.decisions,
            checklist=data.checklist,
            quality=data.quality,
            reviewed_files=data.reviewed_files,
            limitations=data.limitations,
        )
        return build_assessment(stamped)

    def _inputs(self, project_id: str, project_name: str, review_id: str) -> AssessmentInput:
        with self._sessions() as session:
            review = session.get(Review, review_id)
            if review is None or review.project_id != project_id:
                raise ReleaseRejected(404, "That review is not part of this repository.")
            findings = list(
                session.scalars(select(ReviewFinding).where(ReviewFinding.review_id == review_id))
            )
            finding_ids = [item.id for item in findings]
            decisions = []
            if finding_ids:
                decisions = list(
                    session.scalars(
                        select(FindingDecision).where(FindingDecision.finding_id.in_(finding_ids))
                    )
                )
            checklist = list(
                session.scalars(
                    select(ReleaseChecklistDecision).where(
                        ReleaseChecklistDecision.review_id == review_id
                    )
                )
            )
            runs = list(
                session.scalars(
                    select(QualityCheckRun)
                    .where(QualityCheckRun.project_id == project_id)
                    .order_by(QualityCheckRun.created_at.desc())
                )
            )
            return AssessmentInput(
                project_id=project_id,
                project_name=project_name,
                review_id=review_id,
                review_status=review.status,
                base_ref=review.base_ref or "",
                head_sha=review.head_ref or "",
                repository_head_sha="",
                dirty=False,
                generated_at=datetime.now(UTC),
                model=ModelInput(
                    name=review.model_name,
                    context_length=review.context_length,
                    temperature=review.temperature if review.temperature is not None else 0.0,
                    max_output_tokens=review.max_output_tokens or 0,
                    timeout_seconds=int(review.timeout_seconds or 0),
                ),
                findings=tuple(
                    FindingInput(item.id, item.severity, item.title, item.file_path, item.category)
                    for item in findings
                ),
                decisions=tuple(
                    DecisionInput(item.finding_id, item.decision, item.reason, item.reviewer_label)
                    for item in decisions
                ),
                checklist=tuple(
                    ChecklistInput(item.item_key, item.status, item.reason, item.reviewer_label)
                    for item in checklist
                ),
                quality=_quality(runs, review_id),
                reviewed_files=tuple(_strings(review.reviewed_json)),
                limitations=tuple(_strings(review.limitations_json)),
            )

    def _row(self, report_id: str) -> ReleaseReport:
        with self._sessions() as session:
            row = session.get(ReleaseReport, report_id)
            if row is None:
                raise ReleaseRejected(404, "That release report is not stored.")
            session.expunge(row)
            return row


def _quality(runs: list[QualityCheckRun], review_id: str) -> tuple[QualityInput, ...]:
    selected: dict[str, str] = {}
    for run in runs:
        tool = run.tool or ""
        result = run.result or ""
        if tool not in _QUALITY_TOOLS or tool in selected:
            continue
        if run.review_id not in {None, review_id}:
            continue
        if result not in _QUALITY_RESULTS:
            continue
        selected[tool] = result
    return tuple(QualityInput(tool, selected[tool]) for tool in _QUALITY_TOOLS if tool in selected)


def _decision_text(body: FindingDecisionWrite) -> tuple[str, str]:
    return _plain(body.reason, 500, "Reason"), _plain(body.reviewer, 80, "Reviewer")


def _require_identity(reason: str, reviewer: str, label: str) -> tuple[str, str]:
    if reason == "" or reviewer == "":
        raise ReleaseRejected(422, f"{label} needs a reason and a reviewer.")
    return reason, reviewer


def _plain(value: str, limit: int, name: str) -> str:
    text = value.strip()
    if any(ord(char) < 32 for char in text):
        raise ReleaseRejected(422, f"{name} must be plain text.")
    if len(text) > limit:
        raise ReleaseRejected(422, f"{name} is too long.")
    return text


def _strings(raw: str | None) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]
