"""Read stored rows. Phase 0 does not seed reviews or findings."""

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models.project import Project
from app.models.quality import QualityCheckRun
from app.models.release import ReleaseReport
from app.models.review import Review

SessionFactory = sessionmaker[Session]


def ping(session_factory: SessionFactory) -> bool:
    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


def list_projects(session_factory: SessionFactory) -> list[Project]:
    with session_factory() as session:
        return list(session.scalars(select(Project).order_by(Project.created_at.desc())))


def list_reviews(session_factory: SessionFactory) -> list[Review]:
    with session_factory() as session:
        return list(session.scalars(select(Review).order_by(Review.created_at.desc())))


def list_quality_checks(session_factory: SessionFactory) -> list[QualityCheckRun]:
    with session_factory() as session:
        statement = select(QualityCheckRun).order_by(QualityCheckRun.created_at.desc())
        return list(session.scalars(statement))


def list_release_reports(session_factory: SessionFactory) -> list[ReleaseReport]:
    with session_factory() as session:
        statement = select(ReleaseReport).order_by(ReleaseReport.created_at.desc())
        return list(session.scalars(statement))
