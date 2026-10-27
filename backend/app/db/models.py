"""Local SQLite tables. Rows are written only by DevPilot services, never seeded."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewRecord(Base):
    """A review record stored on this machine."""

    __tablename__ = "reviews"
    __table_args__ = (Index("ix_reviews_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False)
    repository_path: Mapped[str] = mapped_column(String(4096), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")


class FindingRecord(Base):
    """A schema-checked finding. Raw model output is not stored."""

    __tablename__ = "review_findings"
    __table_args__ = (Index("ix_review_findings_review_id", "review_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), nullable=False)
    path: Mapped[str] = mapped_column(String(4096), nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    uncertain: Mapped[bool] = mapped_column(Boolean, nullable=False)
