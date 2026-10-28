"""Quality-check contracts. A run accepts a saved tool id, not a shell string."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

QualityStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
QualityResult = Literal["pass", "fail", "skipped", "timed_out"]
ToolName = Literal["phpcs", "phpstan", "phpunit", "composer", "magento"]
CommandArg = Annotated[str, Field(min_length=1, max_length=240)]


class QualityCheckCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=36)
    review_id: str | None = Field(default=None, max_length=36)


class QualityTool(BaseModel):
    tool: ToolName
    label: str
    available: bool
    files: list[str]
    suggested_argv: list[str]
    saved_argv: list[str]
    reason: str | None


class QualityCatalog(BaseModel):
    project_id: str
    working_directory: str
    warning: str
    tools: list[QualityTool]


class QualityCommandWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: ToolName
    argv: list[CommandArg] = Field(min_length=1, max_length=24)


class QualityCommandSaved(BaseModel):
    project_id: str
    tool: ToolName
    argv: list[str]
    updated_at: datetime


class QualityRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: ToolName
    confirmed: bool
    review_id: str | None = Field(default=None, max_length=36)


class QualityCheckRecord(BaseModel):
    id: str
    project_id: str
    review_id: str | None = None
    status: QualityStatus
    result: QualityResult | None = None
    tool: str | None = None
    command: str | None = None
    argv: list[str] = Field(default_factory=list)
    working_directory: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    note: str | None = None
    created_at: datetime
    origin: Literal["command_result"] = "command_result"


class QualityCheckList(BaseModel):
    items: list[QualityCheckRecord]
