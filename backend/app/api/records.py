"""Read stored projects, reviews, quality checks, and release reports."""

from fastapi import APIRouter, Request

from app.api.repositories import project_summary
from app.schemas.project import ProjectList
from app.schemas.quality import QualityCheckList, QualityCheckRecord
from app.schemas.release import ReleaseReportList, ReleaseReportRecord
from app.schemas.review import ReviewList
from app.services.persistence import (
    list_projects,
    list_quality_checks,
    list_release_reports,
)
from app.services.repository import RepositoryService

router = APIRouter(tags=["records"])


@router.get("/projects", response_model=ProjectList)
def get_projects(request: Request) -> ProjectList:
    rows = list_projects(request.app.state.session_factory)
    service = RepositoryService()
    return ProjectList(items=[project_summary(row, service) for row in rows])


@router.get("/reviews", response_model=ReviewList)
def get_reviews(request: Request) -> ReviewList:
    return ReviewList(items=request.app.state.review_service.list_records())


@router.get("/quality-checks", response_model=QualityCheckList)
def get_quality_checks(request: Request) -> QualityCheckList:
    rows = list_quality_checks(request.app.state.session_factory)
    return QualityCheckList(
        items=[QualityCheckRecord.model_validate(row, from_attributes=True) for row in rows]
    )


@router.get("/release-reports", response_model=ReleaseReportList)
def get_release_reports(request: Request) -> ReleaseReportList:
    rows = list_release_reports(request.app.state.session_factory)
    return ReleaseReportList(
        items=[ReleaseReportRecord.model_validate(row, from_attributes=True) for row in rows]
    )
