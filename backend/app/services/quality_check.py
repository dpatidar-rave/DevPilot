"""Confirmed PHP and Magento checks. Registration and reviews do not call this."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.logging_config import log_event
from app.models.project import Project
from app.models.quality import QualityCheckRun, QualityCommand
from app.models.review import Review
from app.schemas.quality import (
    QualityCatalog,
    QualityCheckRecord,
    QualityCommandSaved,
    QualityResult,
    QualityStatus,
    QualityTool,
    ToolName,
)
from app.services.git_runner import GitError
from app.services.persistence import SessionFactory, get_project
from app.services.quality_policy import (
    TIMEOUTS,
    WARNING,
    MissingToolError,
    QualityCommandError,
    detect_tools,
    display_command,
    resolve_invocation,
    validate_command,
)
from app.services.quality_runner import OUTPUT_LIMIT, Execution, QualityRunner
from app.services.repository import RepositoryService


class QualityRejected(Exception):
    """A safe message for a rejected check. It does not include command output."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class QualityCheckService:
    def __init__(
        self,
        sessions: SessionFactory,
        repositories: RepositoryService | None = None,
        runner: QualityRunner | None = None,
    ) -> None:
        self._sessions = sessions
        self._repositories = repositories or RepositoryService()
        self.runner = runner or QualityRunner()

    def list_records(self, project_id: str | None = None) -> list[QualityCheckRecord]:
        with self._sessions() as session:
            statement = select(QualityCheckRun).order_by(QualityCheckRun.created_at.desc())
            if project_id:
                statement = statement.where(QualityCheckRun.project_id == project_id)
            rows = list(session.scalars(statement))
            return [_record(row) for row in rows]

    def catalog(self, project_id: str) -> QualityCatalog:
        project = self._project(project_id)
        repo = self._repo(project)
        saved = self._saved_commands(project_id)
        tools = [
            QualityTool(
                tool=_tool(item.tool),
                label=item.label,
                available=item.available,
                files=list(item.files),
                suggested_argv=list(item.suggested_argv),
                saved_argv=saved.get(item.tool, []),
                reason=item.reason,
            )
            for item in detect_tools(repo)
        ]
        return QualityCatalog(
            project_id=project_id,
            working_directory=repo.as_posix(),
            warning=WARNING,
            tools=tools,
        )

    def save_command(
        self,
        project_id: str,
        tool: ToolName,
        argv: list[str],
    ) -> QualityCommandSaved:
        project = self._project(project_id)
        repo = self._repo(project)
        try:
            found = validate_command(repo, argv)
        except QualityCommandError as exc:
            raise QualityRejected(422, exc.message) from exc
        if found != tool:
            raise QualityRejected(422, "Save the command for the check it belongs to.")
        now = datetime.now(UTC)
        payload = json.dumps(argv)
        with self._sessions() as session:
            row = session.get(QualityCommand, (project_id, tool))
            if row is None:
                session.add(
                    QualityCommand(
                        project_id=project_id,
                        tool=tool,
                        argv_json=payload,
                        updated_at=now,
                    )
                )
            else:
                row.argv_json = payload
                row.updated_at = now
            session.commit()
        return QualityCommandSaved(
            project_id=project_id,
            tool=tool,
            argv=list(argv),
            updated_at=now,
        )

    def run(
        self,
        project_id: str,
        tool: ToolName,
        confirmed: bool,
        review_id: str | None,
    ) -> QualityCheckRecord:
        if confirmed is not True:
            raise QualityRejected(422, "Confirm the command before DevPilot runs it.")
        project = self._project(project_id)
        self._require_review(project_id, review_id)
        repo = self._repo(project)
        saved = self._load_saved(project_id, tool)
        try:
            validate_command(repo, saved)
            resolved = resolve_invocation(repo, saved)
        except QualityCommandError as exc:
            raise QualityRejected(422, exc.message) from exc
        except MissingToolError as exc:
            return self._store_skipped(project_id, review_id, tool, saved, repo, exc.message)
        try:
            outcome = self.runner.execute(
                resolved,
                repo,
                TIMEOUTS[tool],
                OUTPUT_LIMIT,
                root=repo,
            )
        except QualityCommandError as exc:
            raise QualityRejected(422, exc.message) from exc
        except MissingToolError as exc:
            return self._store_skipped(project_id, review_id, tool, saved, repo, exc.message)
        record = self._store_execution(project_id, review_id, tool, outcome)
        log_event(
            logging.INFO,
            "quality_check_finished",
            project_id=project_id,
            review_id=review_id,
            tool=tool,
            result=record.result,
            exit_code=record.exit_code,
        )
        return record

    def _project(self, project_id: str) -> Project:
        project = get_project(self._sessions, project_id)
        if project is None:
            raise QualityRejected(404, "That repository is not registered.")
        return project

    def _repo(self, project: Project) -> Path:
        try:
            return self._repositories.ensure_registered(project.path)
        except GitError as exc:
            raise QualityRejected(exc.status_code, exc.message) from exc

    def _require_review(self, project_id: str, review_id: str | None) -> None:
        if review_id is None:
            return
        with self._sessions() as session:
            review = session.get(Review, review_id)
            matches = review is not None and review.project_id == project_id
        if not matches:
            raise QualityRejected(422, "Choose a review from this repository.")

    def _saved_commands(self, project_id: str) -> dict[str, list[str]]:
        with self._sessions() as session:
            statement = select(QualityCommand).where(QualityCommand.project_id == project_id)
            rows = list(session.scalars(statement))
            return {row.tool: _argv_or_empty(row.argv_json) for row in rows}

    def _load_saved(self, project_id: str, tool: str) -> list[str]:
        with self._sessions() as session:
            row = session.get(QualityCommand, (project_id, tool))
            raw = row.argv_json if row is not None else None
        if raw is None:
            raise QualityRejected(422, "Save a command for this check before running it.")
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise QualityRejected(
                422,
                "The saved command could not be read. Save it again.",
            ) from exc
        if not isinstance(loaded, list) or not all(isinstance(item, str) for item in loaded):
            raise QualityRejected(422, "The saved command could not be read. Save it again.")
        return loaded

    def _store_skipped(
        self,
        project_id: str,
        review_id: str | None,
        tool: str,
        argv: list[str],
        repo: Path,
        message: str,
    ) -> QualityCheckRecord:
        now = datetime.now(UTC)
        record = self._insert(
            project_id=project_id,
            review_id=review_id,
            tool=tool,
            argv=argv,
            command=display_command(argv),
            working_directory=repo.as_posix(),
            status="completed",
            result="skipped",
            started_at=now,
            finished_at=now,
            duration_ms=0,
            exit_code=None,
            stdout="",
            stderr="",
            output_truncated=False,
            note=message[:500],
        )
        log_event(
            logging.INFO,
            "quality_check_finished",
            project_id=project_id,
            review_id=review_id,
            tool=tool,
            result="skipped",
            exit_code=None,
        )
        return record

    def _store_execution(
        self,
        project_id: str,
        review_id: str | None,
        tool: str,
        outcome: Execution,
    ) -> QualityCheckRecord:
        if outcome.timed_out:
            status, result = "failed", "timed_out"
            note = "The command exceeded the time limit and was stopped."
        elif outcome.exit_code == 0:
            status, result = "completed", "pass"
            note = "Exited 0."
        else:
            status, result = "failed", "fail"
            code = "unknown" if outcome.exit_code is None else str(outcome.exit_code)
            note = f"Exited {code}."
        return self._insert(
            project_id=project_id,
            review_id=review_id,
            tool=tool,
            argv=list(outcome.argv),
            command=display_command(list(outcome.argv)),
            working_directory=outcome.working_directory,
            status=status,
            result=result,
            started_at=outcome.started_at,
            finished_at=outcome.finished_at,
            duration_ms=outcome.duration_ms,
            exit_code=outcome.exit_code,
            stdout=outcome.stdout,
            stderr=outcome.stderr,
            output_truncated=outcome.truncated,
            note=note,
        )

    def _insert(
        self,
        *,
        project_id: str,
        review_id: str | None,
        tool: str,
        argv: list[str],
        command: str,
        working_directory: str,
        status: str,
        result: str,
        started_at: datetime,
        finished_at: datetime,
        duration_ms: int,
        exit_code: int | None,
        stdout: str,
        stderr: str,
        output_truncated: bool,
        note: str,
    ) -> QualityCheckRecord:
        now = datetime.now(UTC)
        row = QualityCheckRun(
            id=str(uuid4()),
            project_id=project_id,
            review_id=review_id,
            status=status,
            note=note[:500],
            created_at=now,
            tool=tool,
            argv_json=json.dumps(argv),
            command_display=command,
            working_directory=working_directory,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            exit_code=exit_code,
            result=result,
            stdout=stdout,
            stderr=stderr,
            output_truncated=output_truncated,
        )
        with self._sessions() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return _record(row)


def mark_interrupted_checks(sessions: SessionFactory) -> None:
    """Close checks left running by a restart. This does not start a command."""
    now = datetime.now(UTC)
    note = "DevPilot restarted before this check finished. It was not run again."
    with sessions() as session:
        statement = select(QualityCheckRun).where(QualityCheckRun.status == "running")
        for row in session.scalars(statement):
            row.status = "failed"
            row.result = "fail"
            row.note = note
            row.finished_at = now
        session.commit()


def _record(row: QualityCheckRun) -> QualityCheckRecord:
        return QualityCheckRecord(
        id=row.id,
        project_id=row.project_id,
        review_id=row.review_id,
        status=_status(row.status),
        result=_result(row.result),
        tool=row.tool,
        command=row.command_display,
        argv=_argv_or_empty(row.argv_json),
        working_directory=row.working_directory,
        started_at=row.started_at,
        finished_at=row.finished_at,
        duration_ms=row.duration_ms,
        exit_code=row.exit_code,
        stdout=row.stdout or "",
        stderr=row.stderr or "",
        output_truncated=bool(row.output_truncated),
        note=row.note,
        created_at=row.created_at,
        origin="command_result",
    )


def _tool(value: str) -> ToolName:
    if value == "phpcs":
        return "phpcs"
    if value == "phpstan":
        return "phpstan"
    if value == "phpunit":
        return "phpunit"
    if value == "composer":
        return "composer"
    if value == "magento":
        return "magento"
    raise QualityRejected(422, "That check is not allowlisted.")


def _status(value: str) -> QualityStatus:
    if value == "pending":
        return "pending"
    if value == "running":
        return "running"
    if value == "completed":
        return "completed"
    if value == "cancelled":
        return "cancelled"
    return "failed"


def _result(value: str | None) -> QualityResult | None:
    if value == "pass":
        return "pass"
    if value == "fail":
        return "fail"
    if value == "skipped":
        return "skipped"
    if value == "timed_out":
        return "timed_out"
    return None


def _argv_or_empty(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, str)]
