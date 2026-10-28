"""Release reports. Phase 0 stores the table and does not generate reports."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
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
