"""DevPilot application factory.

The supported server entry point binds the host from settings and refuses any
non-loopback address. Docs UIs are disabled so the browser does not load a CDN.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response

from app import __version__
from app.api.errors import validation_body
from app.api.router import api_router
from app.config import Settings, get_settings
from app.db.migrate import init_database
from app.db.session import create_db_engine, create_session_factory
from app.local_policy import loopback_origin_aliases
from app.logging_config import configure_logging, log_event
from app.services.settings_store import overlay_settings

# FastAPI enables tracing, metrics, and logs unless this is set. Export stays off.
TELEMETRY_DISABLED = {
    "tracing": False,
    "metrics": False,
    "logs": False,
    "operation_spans": False,
    "auto_configure": False,
}


def create_app(settings: Settings | None = None) -> FastAPI:
    active = settings if settings is not None else get_settings()
    configure_logging(active)
    init_database(active.database_url)
    engine = create_db_engine(active.database_url)
    sessions = create_session_factory(engine)
    effective = overlay_settings(active, sessions)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        del app
        yield
        engine.dispose()

    app = FastAPI(
        title="DevPilot",
        version=__version__,
        description="Local-only API. Inference stays on a loopback Ollama process.",
        debug=False,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
        telemetry=TELEMETRY_DISABLED,
    )
    app.state.engine = engine
    app.state.session_factory = sessions
    app.state.settings = effective

    @app.middleware("http")
    async def log_and_protect(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                logging.ERROR,
                "request_failed",
                method=request.method,
                path=request.url.path,
            )
            raise
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        log_event(
            logging.INFO,
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        )
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=loopback_origin_aliases(effective.frontend_origin),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "::1"],
    )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        del request
        return JSONResponse(status_code=422, content=validation_body(exc))

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException):
            detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
            return JSONResponse(status_code=exc.status_code, content={"detail": detail})
        log_event(
            logging.ERROR,
            "unhandled_error",
            error_type=type(exc).__name__,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": (
                    "The local DevPilot service hit an unexpected error. "
                    "Check the local log and retry."
                )
            },
        )

    app.include_router(api_router)
    log_event(
        logging.INFO,
        "startup",
        host=effective.host,
        port=effective.port,
        model=effective.model_name,
        provider="ollama",
    )
    return app


def serve() -> None:
    """Bind the API to the configured loopback address."""
    try:
        settings = get_settings()
    except ValidationError as exc:
        messages = "; ".join(str(error["msg"]) for error in exc.errors())
        print(f"DevPilot refused to start. {messages}", file=sys.stderr)
        raise SystemExit(1) from exc
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        proxy_headers=False,
        forwarded_allow_ips=None,
        server_header=False,
        date_header=False,
        access_log=False,
        log_level=settings.log_level.lower(),
    )
