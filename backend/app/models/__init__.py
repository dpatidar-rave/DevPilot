"""Import models so Alembic and metadata see every table."""

from app.models.project import Project
from app.models.quality import QualityCheckRun, QualityCommand
from app.models.release import ReleaseReport
from app.models.review import Review, ReviewFinding
from app.models.selection import ReviewFileSelection
from app.models.setting import AppSetting

__all__ = [
    "AppSetting",
    "Project",
    "QualityCheckRun",
    "QualityCommand",
    "ReleaseReport",
    "Review",
    "ReviewFileSelection",
    "ReviewFinding",
]
