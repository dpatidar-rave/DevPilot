"""API router. Review execution routes are not mounted in Phase 0."""

from fastapi import APIRouter

from app.api import health, records, settings

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(settings.router)
api_router.include_router(records.router)
