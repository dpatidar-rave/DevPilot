"""Health response. Availability stays not_checked until a review is started."""

from typing import Literal

from pydantic import BaseModel, Field


class LocalAiStatus(BaseModel):
    provider: Literal["ollama"] = "ollama"
    endpoint: str
    model: str
    context_length: int
    temperature: float
    max_output_tokens: int
    timeout_seconds: float
    keep_alive: Literal["10m"] = "10m"
    max_concurrent_requests: Literal[1] = 1
    availability: Literal["not_checked"] = "not_checked"
    external_providers: list[str] = Field(default_factory=list)
    large_model_confirmed: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: Literal["ok", "error"]
    database_message: str | None = None
    bind_host: str
    ai: LocalAiStatus
