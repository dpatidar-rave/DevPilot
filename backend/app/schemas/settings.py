"""Settings contract. The provider cannot be changed."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    model_name: str | None = Field(default=None, alias="model")
    context_length: int | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    timeout_seconds: float | None = None
    ollama_endpoint: str | None = None
    large_model_confirmed: bool | None = None


class SettingsResponse(BaseModel):
    provider: Literal["ollama"] = "ollama"
    model: str
    context_length: int
    temperature: float
    max_output_tokens: int
    timeout_seconds: float
    keep_alive: Literal["10m"] = "10m"
    ollama_endpoint: str
    max_concurrent_requests: Literal[1] = 1
    large_model_confirmed: bool
    availability: Literal["not_checked"] = "not_checked"
    external_providers: list[str] = Field(default_factory=list)


class FieldError(BaseModel):
    field: str
    message: str


class SettingsErrorBody(BaseModel):
    detail: str
    errors: list[FieldError]
