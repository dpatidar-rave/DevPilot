"""Local health. This route does not contact Ollama."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.schemas.health import HealthResponse, LocalAiStatus
from app.services.persistence import ping

router = APIRouter(tags=["health"])

_DATABASE_ERROR = (
    "SQLite is unavailable. Check the local database file and permissions, then retry."
)


def build_health(request: Request, *, database_ok: bool) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok" if database_ok else "degraded",
        version=__version__,
        database="ok" if database_ok else "error",
        database_message=None if database_ok else _DATABASE_ERROR,
        bind_host=settings.host,
        ai=LocalAiStatus(
            endpoint=settings.ollama_endpoint,
            model=settings.model_name,
            context_length=settings.context_length,
            temperature=settings.temperature,
            max_output_tokens=settings.max_output_tokens,
            timeout_seconds=settings.timeout_seconds,
            large_model_confirmed=settings.large_model_confirmed,
        ),
    )


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> JSONResponse:
    database_ok = ping(request.app.state.session_factory)
    body = build_health(request, database_ok=database_ok)
    status_code = 200 if database_ok else 503
    return JSONResponse(status_code=status_code, content=body.model_dump())
