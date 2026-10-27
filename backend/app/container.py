"""Wired services for one local process."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.services.model.ollama import OllamaClient
from app.services.persistence.service import PersistenceService
from app.services.quality_check.service import QualityCheckService
from app.services.release_report.service import ReleaseReportService
from app.services.repository.service import RepositoryService
from app.services.review.service import ReviewService
from app.security.command_runner import CommandRunner
from app.services.review.jobs import ReviewJobManager


@dataclass
class ServiceContainer:
    """Dependencies constructed in `create_app` and reused by routes."""

    settings: Settings
    persistence: PersistenceService
    repository: RepositoryService
    ollama: OllamaClient
    review: ReviewService
    quality: QualityCheckService
    reports: ReleaseReportService
    runner: CommandRunner
    jobs: ReviewJobManager
