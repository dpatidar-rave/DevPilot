"""HTTP handlers. Business rules stay in services."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.schemas import (
    DatabaseStatusResponse,
    FindingResponse,
    HealthResponse,
    InspectionResponse,
    InspectRequest,
    ModelConfigurationResponse,
    QualityCheckListResponse,
    QualityCheckResponse,
    ReleaseReportResponse,
    ReviewJobResponse,
    ReviewListResponse,
    ReviewResponse,
    StartReviewRequest,
    SystemStatusResponse,
)
from app.container import ServiceContainer
from app.errors import DatabaseNotReady
from app.security.loopback import DATABASE_RETRY_INSTRUCTIONS
from app.services.model.policy import KEEP_ALIVE, LARGE_MODEL_WARNING, is_large_model
from app.services.persistence.service import StoredFinding, StoredReview
from app.services.review.jobs import ReviewJob
from app.services.review.schema import ValidatedFinding

router = APIRouter()


def get_container(request: Request) -> ServiceContainer:
    """Return the services wired at startup."""
    container = request.app.state.container
    if not isinstance(container, ServiceContainer):
        raise RuntimeError("DevPilot services are not configured.")
    return container


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Liveness for the local API. This does not contact Ollama."""
    settings = get_container(request).settings
    return HealthResponse(
        status="ok",
        bind_host=settings.host,
        data_store="sqlite-local",
        ai_provider="ollama-local",
        fallback_used=False,
    )


@router.get("/system/status", response_model=SystemStatusResponse)
def system_status(request: Request) -> SystemStatusResponse:
    """Report local configuration. This handler does not contact Ollama."""
    container = get_container(request)
    settings = container.settings
    database_ready = container.persistence.database_ready()
    if database_ready:
        database = DatabaseStatusResponse(ready=True, error=None, retry=[])
    else:
        database = DatabaseStatusResponse(
            ready=False,
            error="Local SQLite is not ready.",
            retry=list(DATABASE_RETRY_INSTRUCTIONS),
        )
    large = is_large_model(settings.model_name)
    return SystemStatusResponse(
        api="ok",
        bind_host=settings.host,
        ai_provider="ollama-local",
        fallback_used=False,
        database=database,
        model=ModelConfigurationResponse(
            name=settings.model_name,
            context_length=settings.context_length,
            temperature=settings.temperature,
            max_output_tokens=settings.max_output_tokens,
            timeout_seconds=settings.ollama_timeout_seconds,
            keep_alive=KEEP_ALIVE,
            endpoint=settings.ollama_base_url,
            availability="not_checked",
            large_model=large,
            memory_warning=LARGE_MODEL_WARNING if large else None,
        ),
    )


@router.get("/reviews", response_model=ReviewListResponse)
def list_reviews(request: Request) -> ReviewListResponse:
    """Return stored reviews. An empty database returns an empty list."""
    container = get_container(request)
    _require_database(container)
    return ReviewListResponse(reviews=[_review_response(item) for item in container.persistence.list_reviews()])


@router.get("/release-report", response_model=ReleaseReportResponse)
def release_report(request: Request) -> ReleaseReportResponse:
    """Build a report from stored rows only."""
    container = get_container(request)
    _require_database(container)
    report = container.reports.build()
    return ReleaseReportResponse(
        records=[_review_response(item) for item in report.records],
        summary=report.summary,
        ai_provider=report.ai_provider,
        fallback_used=report.fallback_used,
    )


@router.get("/quality-checks", response_model=QualityCheckListResponse)
def quality_checks(request: Request) -> QualityCheckListResponse:
    """List known checks. This handler does not run them."""
    checks = get_container(request).quality.list_checks()
    return QualityCheckListResponse(
        checks=[
            QualityCheckResponse(
                check_id=item.check_id,
                description=item.description,
                execution=item.execution,
                requires_explicit_approval=item.requires_explicit_approval,
                executed=item.executed,
            )
            for item in checks
        ]
    )


@router.post("/repository/inspect", response_model=InspectionResponse)
def inspect_repository(body: InspectRequest, request: Request) -> InspectionResponse:
    """Run allowlisted git inspection after an explicit approval flag from the user."""
    inspection = get_container(request).repository.inspect(body.path, approved=body.approved)
    return InspectionResponse(
        path=inspection.path,
        read_only=True,
        inside_work_tree=inspection.inside_work_tree,
        branch=inspection.branch,
        status_porcelain=inspection.status_porcelain,
        truncated=inspection.truncated,
    )


@router.post("/reviews/start", response_model=ReviewJobResponse)
def start_review(body: StartReviewRequest, request: Request) -> ReviewJobResponse:
    """Start a review. This is the first point that may contact Ollama."""
    job = get_container(request).jobs.start(
        body.path,
        approved=body.approved,
        confirm_large_model=body.confirm_large_model,
    )
    return _job_response(job)


@router.get("/reviews/jobs/{job_id}", response_model=ReviewJobResponse)
def review_job(job_id: str, request: Request) -> ReviewJobResponse:
    """Return the in-memory review status. This does not call the model."""
    try:
        job = get_container(request).jobs.get(job_id)
    except KeyError:
        return _missing_job()
    return _job_response(job)


@router.post("/reviews/jobs/{job_id}/cancel", response_model=ReviewJobResponse)
def cancel_review(job_id: str, request: Request) -> ReviewJobResponse:
    """Ask the running review to stop. Model text is not executed."""
    try:
        job = get_container(request).jobs.cancel(job_id)
    except KeyError:
        return _missing_job()
    return _job_response(job)


def _missing_job() -> ReviewJobResponse:
    from fastapi import HTTPException

    raise HTTPException(
        status_code=404,
        detail={
            "message": "That review is not running in this process.",
            "executed": False,
            "retry": [],
        },
    )


def _require_database(container: ServiceContainer) -> None:
    if not container.persistence.database_ready():
        raise DatabaseNotReady()


def _review_response(item: StoredReview) -> ReviewResponse:
    return ReviewResponse(
        id=item.id,
        created_at=item.created_at,
        repository_path=item.repository_path,
        status=item.status,
        summary=item.summary,
        findings=[_finding_response(finding) for finding in item.findings],
    )


def _finding_response(item: StoredFinding | ValidatedFinding) -> FindingResponse:
    return FindingResponse(
        path=item.path,
        line_start=item.line_start,
        line_end=item.line_end,
        severity=item.severity,
        category=item.category,
        summary=item.summary,
        confidence=item.confidence,
        uncertain=item.uncertain,
    )


def _job_response(job: ReviewJob) -> ReviewJobResponse:
    return ReviewJobResponse(
        id=job.id,
        status=job.status,
        repository_path=job.repository_path,
        message=job.message,
        findings=[_finding_response(item) for item in job.findings],
        errors=list(job.errors),
        setup_instruction=job.setup_instruction,
        retry=list(job.retry),
    )
