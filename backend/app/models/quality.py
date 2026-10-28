"""Quality-check runs. Phase 0 stores the table and does not execute checks."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QualityCheckRun(Base):
    __tablename__ = "quality_check_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_quality_check_runs_status",
        ),
        Index("ix_quality_check_runs_project_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
            name="fk_quality_check_runs_project_id_projects",
        ),
        nullable=False,
    )
    review_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "reviews.id",
            ondelete="SET NULL",
            name="fk_quality_check_runs_review_id_reviews",
        ),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
