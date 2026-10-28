"""Release-readiness contract. A client cannot set readiness or mark a release ready."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReleaseStatus = Literal["draft", "ready", "archived"]
Readiness = Literal["blocked", "needs_review", "ready_for_human_approval"]
ChecklistStatus = Literal["pending", "passed", "failed", "waived", "not_applicable"]
FindingDispositionName = Literal["dismissed", "confirmed", "waived"]


class ReleaseReportGenerate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=36)
    review_id: str = Field(min_length=1, max_length=36)


class FindingDecisionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: FindingDispositionName
    reason: str = Field(default="", max_length=500)
    reviewer: str = Field(default="", max_length=80)


class ChecklistDecisionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ChecklistStatus
    reason: str = Field(default="", max_length=500)
    reviewer: str = Field(default="", max_length=80)


class ReleaseWaiver(BaseModel):
    text: str
    reason: str
    reviewer: str


class ChecklistItem(BaseModel):
    key: str
    label: str
    status: ChecklistStatus
    evidence: str
    reason: str = ""
    reviewer: str = ""


class FindingDisposition(BaseModel):
    id: str
    severity: str
    title: str
    file_path: str
    decision: str = ""
    reason: str = ""
    reviewer: str = ""


class QualityEvidence(BaseModel):
    tool: str
    result: str


class ModelSnapshot(BaseModel):
    name: str
    context_length: int
    temperature: float
    max_output_tokens: int
    timeout_seconds: int


class ReleaseAssessment(BaseModel):
    readiness: Readiness
    statement: str
    blockers: list[str]
    warnings: list[str]
    passed: list[str]
    waivers: list[ReleaseWaiver]
    missing: list[str]
    checklist: list[ChecklistItem]
    findings: list[FindingDisposition]
    quality: list[QualityEvidence]
    model: ModelSnapshot
    project_id: str
    project_name: str
    review_id: str
    review_status: str
    base_ref: str
    head_sha: str
    repository_head_sha: str
    dirty: bool
    generated_at: datetime
    limitations: list[str]


class ReleaseReportRecord(BaseModel):
    id: str
    project_id: str
    review_id: str | None = None
    title: str
    status: ReleaseStatus
    readiness: Readiness | None = None
    note: str | None = None
    head_sha: str | None = None
    created_at: datetime


class ReleaseReportList(BaseModel):
    items: list[ReleaseReportRecord]


class ReleaseReportDetail(ReleaseAssessment):
    id: str
    title: str
    status: ReleaseStatus
