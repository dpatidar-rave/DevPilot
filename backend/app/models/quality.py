"""Saved quality commands and the runs a person confirmed."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QualityCommand(Base):
    __tablename__ = "quality_commands"
    __table_args__ = (
        CheckConstraint(
            "tool IN ('phpcs', 'phpstan', 'phpunit', 'composer', 'magento')",
            name="ck_quality_commands_tool",
        ),
        Index("ix_quality_commands_project_id", "project_id"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey(
            "projects.id",
            ondelete="CASCADE",
            name="fk_quality_commands_project_id_projects",
        ),
        primary_key=True,
    )
    tool: Mapped[str] = mapped_column(String(32), primary_key=True)
    argv_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


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
    tool: Mapped[str | None] = mapped_column(String(32), nullable=True)
    argv_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    command_display: Mapped[str | None] = mapped_column(Text, nullable=True)
    working_directory: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_truncated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
    )
