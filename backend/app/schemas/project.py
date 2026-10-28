"""Project contract. Creation is defined here and not mounted in Phase 0."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
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


class ProjectList(BaseModel):
    items: list[ProjectRecord]
