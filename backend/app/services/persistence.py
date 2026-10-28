"""Read and write stored rows. Nothing is seeded."""

from datetime import UTC, datetime

from sqlalchemy import delete, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.models.project import Project
from app.models.quality import QualityCheckRun
from app.models.release import ReleaseReport
from app.models.review import Review
from app.models.selection import ReviewFileSelection

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


def get_project(session_factory: SessionFactory, project_id: str) -> Project | None:
    with session_factory() as session:
        project = session.get(Project, project_id)
        if project is not None:
            session.expunge(project)
        return project


def add_project(session_factory: SessionFactory, project: Project) -> None:
    with session_factory() as session:
        session.add(project)
        session.commit()


def selected_paths(session_factory: SessionFactory, project_id: str) -> list[str]:
    with session_factory() as session:
        statement = (
            select(ReviewFileSelection.path)
            .where(ReviewFileSelection.project_id == project_id)
            .order_by(ReviewFileSelection.path)
        )
        return list(session.scalars(statement))


def replace_selection(session_factory: SessionFactory, project_id: str, paths: list[str]) -> None:
    now = datetime.now(UTC)
    with session_factory() as session:
        session.execute(
            delete(ReviewFileSelection).where(ReviewFileSelection.project_id == project_id)
        )
        session.add_all(
            [
                ReviewFileSelection(project_id=project_id, path=path, updated_at=now)
                for path in paths
            ]
        )
        session.commit()
