"""Files the user has chosen to include in a later review."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewFileSelection(Base):
    __tablename__ = "review_file_selections"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    path: Mapped[str] = mapped_column(String(1024), primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
