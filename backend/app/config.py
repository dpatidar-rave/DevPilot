"""Environment-backed settings. There is no hosted-model configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.local_policy import (
    OLLAMA_KEEP_ALIVE,
    canonical_directory,
    canonical_sqlite_url,
    validate_bind_host,
    validate_frontend_origin,
    validate_model_name,
    validate_ollama_endpoint,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class Settings(BaseSettings):
    """Local process settings.

    Field names are the application settings. Environment variables are explicit
    so an unrelated API key in the environment cannot become configuration.
    """

    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
        protected_namespaces=(),
    )

    host: str = Field(default="127.0.0.1", validation_alias="DEVPILOT_HOST")
    port: int = Field(default=8000, ge=1, le=65535, validation_alias="DEVPILOT_PORT")
    frontend_origin: str = Field(
        default="http://127.0.0.1:5173",
        validation_alias="DEVPILOT_FRONTEND_ORIGIN",
    )
    database_url: str = Field(
        default="sqlite:///./data/devpilot.db",
        validation_alias="DEVPILOT_DATABASE_URL",
    )
    log_level: str = Field(default="INFO", validation_alias="DEVPILOT_LOG_LEVEL")
    log_dir: str = Field(default="./data/logs", validation_alias="DEVPILOT_LOG_DIR")
    ollama_endpoint: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias="DEVPILOT_OLLAMA_ENDPOINT",
    )
    model_name: str = Field(default="qwen2.5-coder:7b", validation_alias="DEVPILOT_MODEL")
    context_length: int = Field(
        default=8192,
        ge=1024,
        le=32768,
        validation_alias="DEVPILOT_CONTEXT_LENGTH",
    )
    temperature: float = Field(
        default=0.1,
        ge=0,
        le=1,
        validation_alias="DEVPILOT_TEMPERATURE",
    )
    max_output_tokens: int = Field(
        default=1800,
        ge=128,
        le=4096,
        validation_alias="DEVPILOT_MAX_OUTPUT_TOKENS",
    )
    timeout_seconds: float = Field(
        default=180,
        ge=10,
        le=600,
        validation_alias="DEVPILOT_TIMEOUT_SECONDS",
    )
    max_concurrent_inference: int = Field(
        default=1,
        validation_alias="DEVPILOT_MAX_CONCURRENT_INFERENCE",
    )
    large_model_confirmed: bool = Field(
        default=False,
        validation_alias="DEVPILOT_LARGE_MODEL_CONFIRMED",
    )

    @property
    def keep_alive(self) -> str:
        return OLLAMA_KEEP_ALIVE

    @field_validator("host")
    @classmethod
    def host_is_loopback(cls, value: str) -> str:
        return validate_bind_host(value)

    @field_validator("frontend_origin")
    @classmethod
    def origin_is_loopback(cls, value: str) -> str:
        return validate_frontend_origin(value)

    @field_validator("database_url")
    @classmethod
    def database_is_local_sqlite(cls, value: str) -> str:
        return canonical_sqlite_url(value, repo_root=str(REPO_ROOT))

    @field_validator("log_dir")
    @classmethod
    def log_directory_is_local(cls, value: str) -> str:
        return canonical_directory(value, repo_root=str(REPO_ROOT))

    @field_validator("log_level")
    @classmethod
    def log_level_is_known(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in _LOG_LEVELS:
            raise ValueError("DEVPILOT_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL.")
        return level

    @field_validator("ollama_endpoint")
    @classmethod
    def endpoint_is_loopback(cls, value: str) -> str:
        return validate_ollama_endpoint(value)

    @model_validator(mode="after")
    def model_policy(self) -> Self:
        self.model_name = validate_model_name(
            self.model_name,
            large_model_confirmed=self.large_model_confirmed,
        )
        if self.max_concurrent_inference != 1:
            raise ValueError(
                "DEVPILOT_MAX_CONCURRENT_INFERENCE must be 1. "
                "DevPilot runs one local inference request at a time."
            )
        return self


def _env_file() -> Path | None:
    if os.environ.get("DEVPILOT_DISABLE_ENV_FILE") == "1":
        return None
    candidate = REPO_ROOT / ".env"
    if candidate.is_file():
        return candidate
    return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process. Routes should use the app-state copy."""
    env_file = _env_file()
    if env_file is None:
        return Settings(_env_file=None)
    return Settings(_env_file=env_file)
