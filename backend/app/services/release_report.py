"""Release-report boundary. Phase 0 does not generate reports."""

from app.models.release import ReleaseReport
from app.services.persistence import SessionFactory, list_release_reports


class ReleaseReportService:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def list_reports(self) -> list[ReleaseReport]:
        return list_release_reports(self._sessions)
