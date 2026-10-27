"""Load model modules so metadata is complete."""

from app.db.models import FindingRecord, ReviewRecord

__all__ = ["FindingRecord", "ReviewRecord"]
