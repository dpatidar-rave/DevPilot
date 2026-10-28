"""Repository inspection responses. Requests reject extra fields."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DiffScope = Literal["staged", "unstaged", "committed", "untracked"]


class DirectoryListingResponse(BaseModel):
    path: str
    parent: str | None
    directories: list[str]
    truncated: bool


class MagentoResponse(BaseModel):
    detected: bool
    edition: str | None
    magento_version: str | None
    php_version: str | None


class RepositoryDetail(BaseModel):
    id: str
    name: str
    path: str
    created_at: datetime
    updated_at: datetime
    branch: str | None
    detached: bool
    head_sha: str | None
    head_subject: str | None
    committed_at: str | None
    branches: list[str]
    dirty: bool
    uncommitted_warning: str | None
    magento: MagentoResponse


class ChangeFileResponse(BaseModel):
    path: str
    status: str
    skipped: Literal["generated", "sensitive"] | None
    selected: bool


class ChangeSetResponse(BaseModel):
    base: str | None
    branches: list[str]
    staged: list[ChangeFileResponse]
    unstaged: list[ChangeFileResponse]
    committed: list[ChangeFileResponse]
    untracked: list[ChangeFileResponse]
    dirty: bool
    truncated: bool
    uncommitted_warning: str | None
    selected_paths: list[str]


class DiffLineResponse(BaseModel):
    kind: Literal["add", "delete", "context", "meta"]
    text: str
    old_line: int | None
    new_line: int | None


class FileDiffResponse(BaseModel):
    path: str
    scope: DiffScope
    binary: bool
    truncated: bool
    skipped: Literal["generated", "sensitive"] | None
    language: str | None
    lines: list[DiffLineResponse]


class SelectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(max_length=400)
    base: str | None = Field(default=None, max_length=200)


class SelectionResponse(BaseModel):
    paths: list[str]
