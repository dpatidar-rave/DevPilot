"""FastAPI application restricted to localhost."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import Settings, get_settings
from app.container import ServiceContainer
from app.db.session import make_engine, make_session_factory
from app.errors import DatabaseNotReady
from app.security.command_gate import CommandRejected
from app.security.command_runner import CommandRunner
from app.security.loopback import DATABASE_RETRY_INSTRUCTIONS, LOCAL_CORS_ORIGINS
from app.services.model.errors import InferenceBusy, ModelPolicyError
from app.services.model.inference import ModelOptions
from app.services.model.ollama import OllamaClient
from app.services.model.ollama_inference import OllamaInference
from app.services.model.policy import KEEP_ALIVE, is_large_model
from app.services.persistence.service import PersistenceService
from app.services.quality_check.service import QualityCheckService
from app.services.release_report.service import ReleaseReportService
from app.services.repository.service import RepositoryPathError, RepositoryService
from app.services.review.jobs import ReviewJobManager
from app.services.review.service import ReviewService


def create_app(
    settings: Settings | None = None,
    ollama: OllamaClient | None = None,
    runner: CommandRunner | None = None,
) -> FastAPI:
    """Build the API. Hosted model clients cannot be injected."""
    active_settings = settings if settings is not None else get_settings()
    engine = make_engine(active_settings.database_url)
    persistence = PersistenceService(make_session_factory(engine))
    active_runner = runner if runner is not None else CommandRunner()
    active_ollama = ollama if ollama is not None else OllamaClient(active_settings.ollama_base_url)
    repository = RepositoryService(active_runner)
    options = ModelOptions(
        model=active_settings.model_name,
        context_length=active_settings.context_length,
        temperature=active_settings.temperature,
        max_output_tokens=active_settings.max_output_tokens,
        timeout_seconds=active_settings.ollama_timeout_seconds,
        keep_alive=KEEP_ALIVE,
        endpoint=active_settings.ollama_base_url,
        large_model=is_large_model(active_settings.model_name),
    )
    container = ServiceContainer(
        settings=active_settings,
        persistence=persistence,
        repository=repository,
        ollama=active_ollama,
        review=ReviewService(),
        quality=QualityCheckService(),
        reports=ReleaseReportService(persistence),
        runner=active_runner,
        jobs=ReviewJobManager(
            repository,
            OllamaInference(active_ollama),
            persistence,
            options,
        ),
    )
    app = FastAPI(title="DevPilot", docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
    app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(LOCAL_CORS_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    _register_exception_handlers(app)
    app.include_router(router, prefix="/api")
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CommandRejected)
    def command_rejected(_request: object, exc: CommandRejected) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"message": str(exc), "executed": False, "retry": []},
        )

    @app.exception_handler(RepositoryPathError)
    def repository_path_error(_request: object, exc: RepositoryPathError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"message": str(exc), "executed": False, "retry": []},
        )

    @app.exception_handler(DatabaseNotReady)
    def database_not_ready(_request: object, _exc: DatabaseNotReady) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "message": "Local SQLite is not ready.",
                "executed": False,
                "retry": list(DATABASE_RETRY_INSTRUCTIONS),
            },
        )

    @app.exception_handler(ModelPolicyError)
    def model_policy_error(_request: object, exc: ModelPolicyError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"message": str(exc), "executed": False, "retry": []},
        )

    @app.exception_handler(InferenceBusy)
    def inference_busy(_request: object, exc: InferenceBusy) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"message": str(exc), "executed": False, "retry": []},
        )


app = create_app()
