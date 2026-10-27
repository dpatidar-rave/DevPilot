"""Store and list review records in local SQLite."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import FindingRecord, ReviewRecord

logger = logging.getLogger("devpilot.persistence")


@dataclass(frozen=True)
class StoredFinding:
    """A stored finding. This is validated review output, not a raw model response."""

    path: str
    line_start: int
    line_end: int
    severity: str
    category: str
    summary: str
    confidence: str
    uncertain: bool


@dataclass(frozen=True)
class StoredReview:
    """A review row as plain data, detached from the session."""

    id: int
    created_at: str
    repository_path: str
    status: str
    summary: str
    findings: tuple[StoredFinding, ...] = ()


@dataclass(frozen=True)
class NewFinding:
    """A validated finding supplied by the review engine."""

    path: str
    line_start: int
    line_end: int
    severity: str
    category: str
    summary: str
    confidence: str
    uncertain: bool


@dataclass(frozen=True)
class NewReview:
    """Values required to store a review. Nothing is invented here."""

    repository_path: str
    status: str
    summary: str


class PersistenceService:
    """SQLite persistence. This service does not seed sample reviews."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def database_ready(self) -> bool:
        """Return whether the migrated reviews table can be queried."""
        try:
            with self._session_factory() as session:
                session.execute(text("SELECT 1 FROM reviews LIMIT 1"))
                session.execute(text("SELECT 1 FROM review_findings LIMIT 1"))
            return True
        except SQLAlchemyError as exc:
            logger.warning("Local SQLite is not ready: %s", exc.__class__.__name__)
            return False

    def list_reviews(self) -> list[StoredReview]:
        """Return stored reviews, newest first. An empty table returns an empty list."""
        with self._session_factory() as session:
            rows = session.scalars(
                select(ReviewRecord).order_by(
                    ReviewRecord.created_at.desc(),
                    ReviewRecord.id.desc(),
                )
            ).all()
            return _load_reviews(session, rows)

    def save_review(
        self,
        review: NewReview,
        findings: tuple[NewFinding, ...] = (),
    ) -> StoredReview:
        """Insert one review supplied by the caller."""
        record = ReviewRecord(
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            repository_path=review.repository_path,
            status=review.status,
            summary=review.summary,
        )
        with self._session_factory() as session:
            session.add(record)
            session.flush()
            for finding in findings:
                session.add(
                    FindingRecord(
                        review_id=record.id,
                        path=finding.path,
                        line_start=finding.line_start,
                        line_end=finding.line_end,
                        severity=finding.severity,
                        category=finding.category,
                        summary=finding.summary,
                        confidence=finding.confidence,
                        uncertain=finding.uncertain,
                    )
                )
            session.commit()
            session.refresh(record)
            stored = _load_reviews(session, [record])
            return stored[0]


def _load_reviews(session: Session, rows: list[ReviewRecord]) -> list[StoredReview]:
    ids = [row.id for row in rows]
    grouped: dict[int, list[FindingRecord]] = {}
    if ids:
        found = session.scalars(select(FindingRecord).where(FindingRecord.review_id.in_(ids))).all()
        for item in found:
            grouped.setdefault(item.review_id, []).append(item)
    return [_to_stored(row, grouped.get(row.id, [])) for row in rows]


def _to_stored(record: ReviewRecord, findings: list[FindingRecord]) -> StoredReview:
    return StoredReview(
        id=record.id,
        created_at=record.created_at,
        repository_path=record.repository_path,
        status=record.status,
        summary=record.summary,
        findings=tuple(_to_finding(item) for item in findings),
    )


def _to_finding(record: FindingRecord) -> StoredFinding:
    return StoredFinding(
        path=record.path,
        line_start=record.line_start,
        line_end=record.line_end,
        severity=record.severity,
        category=record.category,
        summary=record.summary,
        confidence=record.confidence,
        uncertain=bool(record.uncertain),
    )
