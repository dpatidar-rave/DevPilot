"""Quality-check boundary. Phase 0 does not run checks."""

from app.models.quality import QualityCheckRun
from app.services.persistence import SessionFactory, list_quality_checks


class QualityCheckService:
    def __init__(self, sessions: SessionFactory) -> None:
        self._sessions = sessions

    def list_runs(self) -> list[QualityCheckRun]:
        return list_quality_checks(self._sessions)
