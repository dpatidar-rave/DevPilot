"""API router."""

from fastapi import APIRouter

from app.api import health, quality, records, releases, repositories, reviews, settings

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(settings.router)
api_router.include_router(repositories.router)
api_router.include_router(reviews.router)
api_router.include_router(quality.router)
api_router.include_router(releases.router)
api_router.include_router(records.router)
