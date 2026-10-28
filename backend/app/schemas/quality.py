"""Quality-check contract. Execution is not part of Phase 0."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

QualityStatus = Literal["pending", "running", "completed", "failed", "cancelled"]


class QualityCheckCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=36)
    review_id: str | None = Field(default=None, max_length=36)


class QualityCheckRecord(BaseModel):
    id: str
    project_id: str
    review_id: str | None
    status: QualityStatus
    note: str | None
    created_at: datetime


class QualityCheckList(BaseModel):
    items: list[QualityCheckRecord]
