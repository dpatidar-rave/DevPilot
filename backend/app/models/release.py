"""Release reports and the human decisions that feed them.

Generating a report stores a draft snapshot. It does not mark a release ready.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReleaseReport(Base):
    __tablename__ = "release_reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'ready', 'archived')",
            name="ck_release_reports_status",
        ),
        Index("ix_release_reports_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
            name="fk_release_reports_project_id_projects",
        ),
        nullable=False,
    )
    review_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "reviews.id",
            ondelete="SET NULL",
            name="fk_release_reports_review_id_reviews",
        ),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    readiness: Mapped[str | None] = mapped_column(String(32), nullable=True)
    base_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    repository_head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)


class FindingDecision(Base):
    """A person's disposition of one finding. This is not the model's validation flag."""

    __tablename__ = "finding_decisions"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('dismissed', 'confirmed', 'waived')",
            name="ck_finding_decisions_decision",
        ),
    )

    finding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "review_findings.id",
            ondelete="CASCADE",
            name="fk_finding_decisions_finding_id_review_findings",
        ),
        primary_key=True,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    reviewer_label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReleaseChecklistDecision(Base):
    """A person's status for one deployment checklist item."""

    __tablename__ = "release_checklist_decisions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'passed', 'failed', 'waived', 'not_applicable')",
            name="ck_release_checklist_decisions_status",
        ),
        Index("ix_release_checklist_decisions_project_id", "project_id"),
    )

    review_id: Mapped[str] = mapped_column(
        ForeignKey(
            "reviews.id",
            ondelete="CASCADE",
            name="fk_release_checklist_decisions_review_id_reviews",
        ),
        primary_key=True,
    )
    item_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
            name="fk_release_checklist_decisions_project_id_projects",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    reviewer_label: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
