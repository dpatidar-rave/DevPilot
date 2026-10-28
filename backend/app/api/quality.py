"""Read and run confirmed quality checks for one registered repository."""

from fastapi import APIRouter, HTTPException, Request

from app.schemas.quality import (
    QualityCatalog,
    QualityCheckRecord,
    QualityCommandSaved,
    QualityCommandWrite,
    QualityRunRequest,
)
from app.services.quality_check import QualityRejected

router = APIRouter(tags=["quality"])


@router.get("/projects/{project_id}/quality/tools", response_model=QualityCatalog)
def read_quality_tools(project_id: str, request: Request) -> QualityCatalog:
    try:
        return request.app.state.quality_service.catalog(project_id)
    except QualityRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.put("/projects/{project_id}/quality/commands", response_model=QualityCommandSaved)
def save_quality_command(
    project_id: str,
    body: QualityCommandWrite,
    request: Request,
) -> QualityCommandSaved:
    try:
        return request.app.state.quality_service.save_command(project_id, body.tool, body.argv)
    except QualityRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/projects/{project_id}/quality/runs", response_model=QualityCheckRecord)
def run_quality_check(
    project_id: str,
    body: QualityRunRequest,
    request: Request,
) -> QualityCheckRecord:
    try:
        return request.app.state.quality_service.run(
            project_id,
            body.tool,
            body.confirmed,
            body.review_id,
        )
    except QualityRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
