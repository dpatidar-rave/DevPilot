"""Review contracts. A finding below 0.5 confidence must be marked uncertain."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Severity = Literal["critical", "high", "medium", "low", "info"]
ReviewStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
ValidationStatus = Literal["accepted", "rejected", "uncertain"]


class ReviewCreate(BaseModel):
    """A review uses the configured local model. Provider is not an input."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=36)
    base_ref: str = Field(min_length=1, max_length=200)
    head_ref: str = Field(min_length=1, max_length=200)


class FindingContract(BaseModel):
    """Strict shape used before a model finding can be stored."""

    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(min_length=1, max_length=1024)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    severity: Severity
    category: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(ge=0, le=1)
    uncertain: bool

    @model_validator(mode="after")
    def uncertain_when_unreliable(self) -> Self:
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line.")
        if self.confidence < 0.5 and not self.uncertain:
            raise ValueError("Findings below 0.5 confidence must be flagged uncertain.")
        return self


class ReviewStart(BaseModel):
    """Start a review with the configured local model. The model is not an input."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=36)
    base_ref: str = Field(min_length=1, max_length=200)
    paths: list[str] = Field(min_length=1, max_length=40)


class SkippedFile(BaseModel):
    path: str
    reason: str


class FindingResponse(BaseModel):
    """An AI suggestion. It is never a deterministic test result."""

    model_config = ConfigDict(extra="forbid")

    id: str
    stable_key: str
    file_path: str
    scope: str
    start_line: int
    end_line: int
    severity: Severity
    category: str
    title: str
    explanation: str
    evidence: str
    remediation: str
    confidence: float
    uncertain: bool
    needs_human_verification: Literal[True] = True
    evidence_checked: bool
    origin: Literal["ai_suggestion"] = "ai_suggestion"


class ReviewRecord(BaseModel):
    id: str
    project_id: str
    status: ReviewStatus
    base_ref: str | None
    head_ref: str | None
    model: str
    context_length: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None = None
    finding_count: int
    summary: str = ""
    limitations: list[str] = Field(default_factory=list)
    skipped_files: list[SkippedFile] = Field(default_factory=list)
    reviewed_files: list[str] = Field(default_factory=list)
    files_reviewed: int = 0
    files_skipped: int = 0
    chunks_total: int = 0
    chunks_completed: int = 0
    temperature: float | None = None
    max_output_tokens: int | None = None
    timeout_seconds: float | None = None
    keep_alive: str | None = None


class ReviewDetail(ReviewRecord):
    findings: list[FindingResponse] = Field(default_factory=list)


class ReviewList(BaseModel):
    items: list[ReviewRecord]
