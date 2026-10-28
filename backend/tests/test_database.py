"""SQLite migration, permissions, and constraints."""

import stat
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db.sqlite import sqlite_path
from app.main import create_app
from app.models.project import Project
from app.models.review import Review, ReviewFinding

EXPECTED_TABLES = {
    "projects",
    "reviews",
    "review_findings",
    "quality_check_runs",
    "quality_commands",
    "release_reports",
    "finding_decisions",
    "release_checklist_decisions",
    "app_settings",
    "review_file_selections",
}


def test_database_initialization_creates_schema_and_restricts_permissions(
    settings: Settings,
) -> None:
    application = create_app(settings)
    try:
        names = set(inspect(application.state.engine).get_table_names())
    finally:
        application.state.engine.dispose()

    assert EXPECTED_TABLES <= names
    database_file = sqlite_path(settings.database_url)
    assert database_file.is_file()
    assert stat.S_IMODE(database_file.stat().st_mode) == 0o600


def test_migration_is_idempotent(settings: Settings) -> None:
    first = create_app(settings)
    first.state.engine.dispose()
    second = create_app(settings)
    try:
        names = set(inspect(second.state.engine).get_table_names())
    finally:
        second.state.engine.dispose()

    assert EXPECTED_TABLES <= names


def test_fresh_lists_are_empty_without_sample_rows(client: TestClient) -> None:
    assert client.get("/api/projects").json() == {"items": []}
    assert client.get("/api/reviews").json() == {"items": []}
    assert client.get("/api/quality-checks").json() == {"items": []}
    assert client.get("/api/release-reports").json() == {"items": []}


def test_project_round_trip_and_finding_constraints(app: FastAPI, client: TestClient) -> None:
    factory = app.state.session_factory
    now = datetime.now(UTC)
    project_id = str(uuid4())
    review_id = str(uuid4())

    with factory() as session:
        session.add(
            Project(
                id=project_id,
                name="local-repo",
                path="/tmp/devpilot-schema-probe",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            Review(
                id=review_id,
                project_id=project_id,
                status="pending",
                base_ref="main",
                head_ref="topic",
                model_name="qwen2.5-coder:7b",
                context_length=8192,
                created_at=now,
                finding_count=0,
            )
        )
        session.commit()

    with factory() as session:
        session.add(
            _finding(review_id=review_id, confidence=0.2, uncertain=False, created_at=now)
        )
        with pytest.raises(IntegrityError):
            session.commit()

    with factory() as session:
        session.add(
            _finding(review_id=str(uuid4()), confidence=0.9, uncertain=True, created_at=now)
        )
        with pytest.raises(IntegrityError):
            session.commit()

    payload = client.get("/api/projects").json()
    reviews = client.get("/api/reviews").json()
    assert payload["items"][0]["name"] == "local-repo"
    assert payload["items"][0]["path"] == "/tmp/devpilot-schema-probe"
    assert reviews["items"][0]["model"] == "qwen2.5-coder:7b"
    assert reviews["items"][0]["finding_count"] == 0
    assert reviews["items"][0]["status"] == "pending"


def _finding(
    *,
    review_id: str,
    confidence: float,
    uncertain: bool,
    created_at: datetime,
) -> ReviewFinding:
    return ReviewFinding(
        id=str(uuid4()),
        review_id=review_id,
        file_path="probe.php",
        start_line=1,
        end_line=2,
        severity="low",
        category="constraint",
        title="constraint probe",
        summary="constraint probe",
        confidence=confidence,
        uncertain=uncertain,
        validation_status="uncertain",
        created_at=created_at,
    )
