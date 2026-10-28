"""Project contract for registering a local Git working tree."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)
    path: str = Field(min_length=1, max_length=1024)

    @field_validator("path")
    @classmethod
    def path_is_absolute(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("Repository path must be an absolute local path.")
        return value


class ProjectRecord(BaseModel):
    id: str
    name: str
    path: str
    created_at: datetime
    updated_at: datetime


class ProjectSummary(ProjectRecord):
    branch: str | None = None
    detached: bool = False
    head_sha: str | None = None
    head_subject: str | None = None
    dirty: bool = False
    magento: bool = False
    inspection_error: str | None = None


class ProjectList(BaseModel):
    items: list[ProjectSummary]
