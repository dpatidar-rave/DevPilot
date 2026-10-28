"""Read and update local model settings."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.errors import validation_body
from app.schemas.settings import SettingsResponse, SettingsUpdate
from app.services.settings_store import replace_settings, save_settings

router = APIRouter(prefix="/settings", tags=["settings"])


def to_response(request: Request) -> SettingsResponse:
    settings = request.app.state.settings
    return SettingsResponse(
        model=settings.model_name,
        context_length=settings.context_length,
        temperature=settings.temperature,
        max_output_tokens=settings.max_output_tokens,
        timeout_seconds=settings.timeout_seconds,
        ollama_endpoint=settings.ollama_endpoint,
        large_model_confirmed=settings.large_model_confirmed,
    )


@router.get("", response_model=SettingsResponse)
def read_settings(request: Request) -> SettingsResponse:
    return to_response(request)


@router.patch("", response_model=SettingsResponse)
def update_settings(payload: SettingsUpdate, request: Request) -> SettingsResponse | JSONResponse:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return to_response(request)
    try:
        updated = replace_settings(request.app.state.settings, changes)
    except ValidationError as exc:
        return JSONResponse(status_code=422, content=validation_body(exc))
    save_settings(request.app.state.session_factory, changes)
    request.app.state.settings = updated
    return to_response(request)
