"""Release assessment, human decisions, and stored report exports."""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app.schemas.release import (
    ChecklistDecisionWrite,
    FindingDecisionWrite,
    ReleaseAssessment,
    ReleaseReportDetail,
    ReleaseReportGenerate,
)
from app.services.release_report import ReleaseRejected

router = APIRouter(tags=["releases"])


@router.get("/projects/{project_id}/release-assessment", response_model=ReleaseAssessment)
def preview_release(
    project_id: str,
    request: Request,
    review_id: str = Query(min_length=1, max_length=36),
) -> ReleaseAssessment:
    try:
        return request.app.state.release_service.preview(project_id, review_id)
    except ReleaseRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.put(
    "/reviews/{review_id}/findings/{finding_id}/decision",
    response_model=ReleaseAssessment,
)
def save_finding_decision(
    review_id: str,
    finding_id: str,
    body: FindingDecisionWrite,
    request: Request,
) -> ReleaseAssessment:
    try:
        return request.app.state.release_service.save_finding_decision(review_id, finding_id, body)
    except ReleaseRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.put("/reviews/{review_id}/checklist/{item_key}", response_model=ReleaseAssessment)
def save_checklist_decision(
    review_id: str,
    item_key: str,
    body: ChecklistDecisionWrite,
    request: Request,
) -> ReleaseAssessment:
    try:
        return request.app.state.release_service.save_checklist_decision(review_id, item_key, body)
    except ReleaseRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/release-reports", response_model=ReleaseReportDetail, status_code=201)
def create_release_report(body: ReleaseReportGenerate, request: Request) -> ReleaseReportDetail:
    try:
        return request.app.state.release_service.generate(body.project_id, body.review_id)
    except ReleaseRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/release-reports/{report_id}", response_model=ReleaseReportDetail)
def read_release_report(report_id: str, request: Request) -> ReleaseReportDetail:
    try:
        return request.app.state.release_service.read(report_id)
    except ReleaseRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/release-reports/{report_id}/markdown")
def export_release_markdown(report_id: str, request: Request) -> Response:
    try:
        body = request.app.state.release_service.markdown(report_id)
    except ReleaseRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="release-report.md"'},
    )


@router.get("/release-reports/{report_id}/json")
def export_release_json(report_id: str, request: Request) -> Response:
    try:
        body = request.app.state.release_service.json_export(report_id)
    except ReleaseRejected as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="release-report.json"'},
    )
