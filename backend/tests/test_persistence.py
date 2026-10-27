"""Persistence and release reports use stored rows only."""

from __future__ import annotations

from app.db.session import make_engine, make_session_factory
from app.services.persistence.service import NewReview, PersistenceService
from app.services.release_report.service import ReleaseReportService


def test_migrated_database_has_no_seed_reviews(database_url: str) -> None:
    service = _service(database_url)
    assert service.database_ready() is True
    assert service.list_reviews() == []


def test_round_trip_returns_only_the_saved_row(database_url: str) -> None:
    service = _service(database_url)
    saved = service.save_review(
        NewReview(
            repository_path="/work/store",
            status="recorded",
            summary="stored-from-test-only",
        )
    )
    listed = service.list_reviews()
    assert [item.id for item in listed] == [saved.id]
    assert listed[0].summary == "stored-from-test-only"
    assert listed[0].repository_path == "/work/store"


def test_release_report_does_not_invent_records(database_url: str) -> None:
    service = _service(database_url)
    empty = ReleaseReportService(service).build()
    assert empty.records == ()
    assert empty.summary == "No release report data is stored locally."
    assert empty.ai_provider == "ollama-local"
    assert empty.fallback_used is False

    service.save_review(
        NewReview(
            repository_path="/work/store",
            status="recorded",
            summary="stored-from-test-only",
        )
    )
    report = ReleaseReportService(service).build()
    assert len(report.records) == 1
    assert report.records[0].summary == "stored-from-test-only"
    assert report.summary == "1 locally stored review record(s)."
    assert report.fallback_used is False


def _service(database_url: str) -> PersistenceService:
    return PersistenceService(make_session_factory(make_engine(database_url)))
