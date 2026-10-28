"""Review runs and findings. Findings are data, never commands."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_reviews_status",
        ),
        Index("ix_reviews_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE", name="fk_reviews_project_id_projects"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    base_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    head_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    context_length: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    keep_alive: Mapped[str | None] = mapped_column(String(16), nullable=True)
    files_reviewed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    files_skipped: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    chunks_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    chunks_completed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    limitations_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default="[]"
    )
    skipped_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default="[]"
    )
    reviewed_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default="[]"
    )


class ReviewFinding(Base):
    """A stored finding stays unconfirmed unless validation marks it accepted."""

    __tablename__ = "review_findings"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('critical', 'high', 'medium', 'low', 'info')",
            name="ck_review_findings_severity",
        ),
        CheckConstraint(
            "validation_status IN ('accepted', 'rejected', 'uncertain')",
            name="ck_review_findings_validation_status",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_review_findings_confidence",
        ),
        CheckConstraint("start_line >= 1", name="ck_review_findings_start_line"),
        CheckConstraint("end_line >= start_line", name="ck_review_findings_line_range"),
        CheckConstraint(
            "(confidence >= 0.5) OR (uncertain = 1)",
            name="ck_review_findings_uncertain",
        ),
        Index("ix_review_findings_review_id", "review_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    review_id: Mapped[str] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE", name="fk_review_findings_review_id_reviews"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    uncertain: Mapped[bool] = mapped_column(Boolean, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="uncertain",
    )
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    remediation: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    verification: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="needs_review",
        server_default="needs_review",
    )
    stable_key: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default=""
    )
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
