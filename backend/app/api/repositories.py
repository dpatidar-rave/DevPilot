"""Register a local Git working tree and read its changes."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

from app.logging_config import log_event
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectSummary
from app.schemas.repository import (
    ChangeFileResponse,
    ChangeSetResponse,
    DiffLineResponse,
    DirectoryListingResponse,
    FileDiffResponse,
    MagentoResponse,
    RepositoryDetail,
    SelectionResponse,
    SelectionUpdate,
)
from app.services.git_runner import GitError
from app.services.persistence import (
    add_project,
    get_project,
    replace_selection,
    selected_paths,
)
from app.services.repository import (
    UNCOMMITTED_WARNING,
    ChangeFile,
    ChangeGroups,
    Inspection,
    RepositoryService,
)

router = APIRouter(tags=["repositories"])


@router.get("/browse", response_model=DirectoryListingResponse)
def browse_directories(
    path: str | None = Query(default=None, max_length=1024),
) -> DirectoryListingResponse:
    listing = _call(RepositoryService().list_directories, path)
    return DirectoryListingResponse(
        path=listing.path,
        parent=listing.parent,
        directories=listing.directories,
        truncated=listing.truncated,
    )


@router.post("/projects", response_model=RepositoryDetail, status_code=201)
def register_project(body: ProjectCreate, request: Request) -> RepositoryDetail:
    service = RepositoryService()
    repo = _call(service.ensure_work_tree, body.path)
    name = _call(service.display_name, repo, body.name)
    now = datetime.now(UTC)
    project = Project(
        id=str(uuid4()),
        name=name,
        path=repo.as_posix(),
        created_at=now,
        updated_at=now,
    )
    try:
        add_project(request.app.state.session_factory, project)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="That repository path is already registered.",
        ) from exc
    log_event(logging.INFO, "repository_registered", project_id=project.id)
    return _detail(project, _call(service.inspect, repo))


@router.get("/projects/{project_id}", response_model=RepositoryDetail)
def read_project(project_id: str, request: Request) -> RepositoryDetail:
    project = _stored(request, project_id)
    service = RepositoryService()
    repo = _call(service.ensure_registered, project.path)
    return _detail(project, _call(service.inspect, repo))


@router.get("/projects/{project_id}/changes", response_model=ChangeSetResponse)
def read_changes(
    project_id: str,
    request: Request,
    base: str | None = Query(default=None, max_length=200),
) -> ChangeSetResponse:
    project = _stored(request, project_id)
    service = RepositoryService()
    repo = _call(service.ensure_registered, project.path)
    groups = _call(service.changes, repo, base)
    chosen = set(selected_paths(request.app.state.session_factory, project.id))
    return _change_set(groups, chosen)


@router.get("/projects/{project_id}/diff", response_model=FileDiffResponse)
def read_diff(
    project_id: str,
    request: Request,
    scope: str = Query(min_length=1, max_length=32),
    path: str = Query(min_length=1, max_length=1024),
    base: str | None = Query(default=None, max_length=200),
) -> FileDiffResponse:
    project = _stored(request, project_id)
    service = RepositoryService()
    repo = _call(service.ensure_registered, project.path)
    diff = _call(service.file_diff, repo, scope, path, base)
    return FileDiffResponse(
        path=diff.path,
        scope=_scope(diff.scope),
        binary=diff.binary,
        truncated=diff.truncated,
        skipped=_skipped(diff.skipped),
        language=diff.language,
        lines=[
            DiffLineResponse(
                kind=_kind(line.kind),
                text=line.text,
                old_line=line.old_line,
                new_line=line.new_line,
            )
            for line in diff.lines
        ],
    )


@router.put("/projects/{project_id}/selection", response_model=SelectionResponse)
def save_selection(project_id: str, body: SelectionUpdate, request: Request) -> SelectionResponse:
    project = _stored(request, project_id)
    service = RepositoryService()
    repo = _call(service.ensure_registered, project.path)
    groups = _call(service.changes, repo, body.base)
    allowed = service.visible_paths(groups)
    chosen: list[str] = []
    seen: set[str] = set()
    for raw_path in body.paths:
        if raw_path in seen:
            continue
        if raw_path not in allowed:
            raise HTTPException(
                status_code=422,
                detail="Only visible changed files in this repository can be selected.",
            )
        seen.add(raw_path)
        chosen.append(raw_path)
    replace_selection(request.app.state.session_factory, project.id, chosen)
    return SelectionResponse(paths=chosen)


def project_summary(project: Project, service: RepositoryService) -> ProjectSummary:
    base = {
        "id": project.id,
        "name": project.name,
        "path": project.path,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }
    try:
        repo = service.ensure_registered(project.path)
        info = service.inspect(repo)
    except GitError as exc:
        return ProjectSummary(**base, inspection_error=exc.message)
    return ProjectSummary(
        **base,
        branch=info.branch,
        detached=info.detached,
        head_sha=None if info.head is None else info.head.sha[:12],
        head_subject=None if info.head is None else info.head.subject,
        dirty=info.dirty,
        magento=info.magento.detected,
    )


def _stored(request: Request, project_id: str) -> Project:
    project = get_project(request.app.state.session_factory, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="That repository is not registered.")
    return project


def _detail(project: Project, info: Inspection) -> RepositoryDetail:
    warning = UNCOMMITTED_WARNING if info.dirty else None
    return RepositoryDetail(
        id=project.id,
        name=project.name,
        path=project.path,
        created_at=project.created_at,
        updated_at=project.updated_at,
        branch=info.branch,
        detached=info.detached,
        head_sha=None if info.head is None else info.head.sha[:12],
        head_subject=None if info.head is None else info.head.subject,
        committed_at=None if info.head is None else info.head.committed_at,
        branches=info.branches,
        dirty=info.dirty,
        uncommitted_warning=warning,
        magento=MagentoResponse(
            detected=info.magento.detected,
            edition=info.magento.edition,
            magento_version=info.magento.magento_version,
            php_version=info.magento.php_version,
        ),
    )


def _change_set(groups: ChangeGroups, chosen: set[str]) -> ChangeSetResponse:
    def files(items: list[ChangeFile]) -> list[ChangeFileResponse]:
        return [
            ChangeFileResponse(
                path=item.path,
                status=item.status,
                skipped=_skipped(item.skipped),
                selected=item.path in chosen and item.skipped is None,
            )
            for item in items
        ]

    return ChangeSetResponse(
        base=groups.base,
        branches=groups.branches,
        staged=files(groups.staged),
        unstaged=files(groups.unstaged),
        committed=files(groups.committed),
        untracked=files(groups.untracked),
        dirty=groups.dirty,
        truncated=groups.truncated,
        uncommitted_warning=UNCOMMITTED_WARNING if groups.dirty else None,
        selected_paths=sorted(path for path in chosen if path in _visible(groups)),
    )


def _visible(groups: ChangeGroups) -> set[str]:
    paths: set[str] = set()
    for group in (groups.staged, groups.unstaged, groups.committed, groups.untracked):
        paths.update(item.path for item in group if item.skipped is None)
    return paths


def _scope(value: str) -> str:
    if value not in {"staged", "unstaged", "committed", "untracked"}:
        raise HTTPException(
            status_code=422,
            detail="Choose staged, unstaged, committed, or untracked changes.",
        )
    return value


def _skipped(value: str | None) -> str | None:
    if value not in {None, "generated", "sensitive"}:
        return "sensitive"
    return value


def _kind(value: str) -> str:
    if value not in {"add", "delete", "context", "meta"}:
        return "meta"
    return value


_T = TypeVar("_T")


def _call(func: Callable[..., _T], *args: object) -> _T:
    try:
        return func(*args)
    except GitError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
