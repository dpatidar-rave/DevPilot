"""Release reports built only from locally stored review rows."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.persistence.service import PersistenceService, StoredReview


@dataclass(frozen=True)
class ReleaseReport:
    """A report that contains stored records and no invented findings."""

    records: tuple[StoredReview, ...]
    summary: str
    ai_provider: str
    fallback_used: bool


class ReleaseReportService:
    """Build a release report from SQLite. Missing rows stay missing."""

    def __init__(self, persistence: PersistenceService) -> None:
        self._persistence = persistence

    def build(self) -> ReleaseReport:
        """Summarize stored reviews. An empty database produces an empty report."""
        if not self._persistence.database_ready():
            return ReleaseReport(
                records=(),
                summary="No release report data is stored locally.",
                ai_provider="ollama-local",
                fallback_used=False,
            )
        records = tuple(self._persistence.list_reviews())
        if not records:
            summary = "No release report data is stored locally."
        else:
            summary = f"{len(records)} locally stored review record(s)."
        return ReleaseReport(
            records=records,
            summary=summary,
            ai_provider="ollama-local",
            fallback_used=False,
        )
