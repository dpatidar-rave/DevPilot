"""HTTP response models. Fields mirror stored data and local checks."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    bind_host: str
    data_store: str
    ai_provider: str
    fallback_used: bool


class DatabaseStatusResponse(BaseModel):
    ready: bool
    error: Optional[str]
    retry: List[str]


class ModelConfigurationResponse(BaseModel):
    name: str
    context_length: int
    temperature: float
    max_output_tokens: int
    timeout_seconds: float
    keep_alive: str
    endpoint: str
    availability: str
    large_model: bool
    memory_warning: Optional[str]


class SystemStatusResponse(BaseModel):
    api: str
    bind_host: str
    ai_provider: str
    fallback_used: bool
    database: DatabaseStatusResponse
    model: ModelConfigurationResponse


class FindingResponse(BaseModel):
    path: str
    line_start: int
    line_end: int
    severity: str
    category: str
    summary: str
    confidence: str
    uncertain: bool


class ReviewResponse(BaseModel):
    id: int
    created_at: str
    repository_path: str
    status: str
    summary: str
    findings: List[FindingResponse]


class ReviewListResponse(BaseModel):
    reviews: List[ReviewResponse]


class ReleaseReportResponse(BaseModel):
    records: List[ReviewResponse]
    summary: str
    ai_provider: str
    fallback_used: bool


class QualityCheckResponse(BaseModel):
    check_id: str
    description: str
    execution: str
    requires_explicit_approval: bool
    executed: bool


class QualityCheckListResponse(BaseModel):
    checks: List[QualityCheckResponse]


class InspectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    approved: bool


class InspectionResponse(BaseModel):
    path: str
    read_only: bool
    inside_work_tree: bool
    branch: str
    status_porcelain: str
    truncated: bool


class StartReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
    approved: bool
    confirm_large_model: bool = False


class ReviewJobResponse(BaseModel):
    id: str
    status: str
    repository_path: str
    message: str
    findings: List[FindingResponse]
    errors: List[str]
    setup_instruction: Optional[str]
    retry: List[str]


class ErrorResponse(BaseModel):
    message: str
    executed: bool = False
    retry: List[str] = Field(default_factory=list)
    setup_instruction: Optional[str] = None
