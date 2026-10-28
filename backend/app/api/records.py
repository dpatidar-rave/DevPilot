"""Read stored projects, reviews, quality checks, and release reports."""

from fastapi import APIRouter, Request

from app.schemas.project import ProjectList, ProjectRecord
from app.schemas.quality import QualityCheckList, QualityCheckRecord
from app.schemas.release import ReleaseReportList, ReleaseReportRecord
from app.schemas.review import ReviewList, ReviewRecord
from app.services.persistence import (
    list_projects,
    list_quality_checks,
    list_release_reports,
    list_reviews,
)

router = APIRouter(tags=["records"])


@router.get("/projects", response_model=ProjectList)
def get_projects(request: Request) -> ProjectList:
    rows = list_projects(request.app.state.session_factory)
    return ProjectList(
        items=[ProjectRecord.model_validate(row, from_attributes=True) for row in rows]
    )


@router.get("/reviews", response_model=ReviewList)
def get_reviews(request: Request) -> ReviewList:
    rows = list_reviews(request.app.state.session_factory)
    return ReviewList(
        items=[
            ReviewRecord.model_validate(
                {
                    "id": row.id,
                    "project_id": row.project_id,
                    "status": row.status,
                    "base_ref": row.base_ref,
                    "head_ref": row.head_ref,
                    "model": row.model_name,
                    "context_length": row.context_length,
                    "created_at": row.created_at,
                    "started_at": row.started_at,
                    "finished_at": row.finished_at,
                    "error_code": row.error_code,
                    "finding_count": row.finding_count,
                }
            )
            for row in rows
        ]
    )


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
