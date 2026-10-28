"""Release-report contract. Generation is not part of Phase 0."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReleaseStatus = Literal["draft", "ready", "archived"]


class ReleaseReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=36)
    review_id: str | None = Field(default=None, max_length=36)
    title: str = Field(min_length=1, max_length=200)


class ReleaseReportRecord(BaseModel):
    id: str
    project_id: str
    review_id: str | None
    title: str
    status: ReleaseStatus
    note: str | None
    created_at: datetime


class ReleaseReportList(BaseModel):
    items: list[ReleaseReportRecord]
