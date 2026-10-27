"""Application settings. Defaults stay on the local machine."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.security.loopback import (
    assert_local_sqlite,
    assert_loopback_host,
    assert_loopback_http_url,
)
from app.services.model.policy import (
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_CONTEXT_LENGTH,
    MAX_TIMEOUT_SECONDS,
    MIN_CONTEXT_LENGTH,
    MIN_TIMEOUT_SECONDS,
    ModelNameRejected,
    assert_local_model_name,
)


def _default_database_url() -> str:
    data_dir = Path(__file__).resolve().parents[1] / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + str(data_dir / "devpilot.sqlite")


class Settings(BaseSettings):
    """Runtime configuration loaded from the environment, not from a dotenv file."""

    model_config = SettingsConfigDict(
        env_prefix="DEVPILOT_",
        extra="ignore",
        env_file=None,
    )

    host: str = "127.0.0.1"
    port: int = 8000
    database_url: str = Field(default_factory=_default_database_url)
    ollama_base_url: str = "http://127.0.0.1:11434"
    model_name: str = DEFAULT_MODEL
    context_length: int = DEFAULT_CONTEXT_LENGTH
    temperature: float = DEFAULT_TEMPERATURE
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    ollama_timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS

    @model_validator(mode="after")
    def enforce_local_only(self) -> Settings:
        self.host = assert_loopback_host(self.host)
        self.ollama_base_url = assert_loopback_http_url(self.ollama_base_url)
        self.database_url = assert_local_sqlite(self.database_url)
        if self.port < 1 or self.port > 65535:
            raise ValueError("Port must be between 1 and 65535.")
        try:
            self.model_name = assert_local_model_name(self.model_name)
        except ModelNameRejected as exc:
            raise ValueError(str(exc)) from exc
        if self.context_length < MIN_CONTEXT_LENGTH or self.context_length > MAX_CONTEXT_LENGTH:
            raise ValueError(
                f"Context length must be between {MIN_CONTEXT_LENGTH} and {MAX_CONTEXT_LENGTH} tokens."
            )
        if self.temperature < 0 or self.temperature > 1:
            raise ValueError("Temperature must be between 0 and 1.")
        if self.max_output_tokens < 1 or self.max_output_tokens > DEFAULT_MAX_OUTPUT_TOKENS:
            raise ValueError(f"Maximum output must be between 1 and {DEFAULT_MAX_OUTPUT_TOKENS} tokens.")
        if (
            self.ollama_timeout_seconds < MIN_TIMEOUT_SECONDS
            or self.ollama_timeout_seconds > MAX_TIMEOUT_SECONDS
        ):
            raise ValueError(
                f"Timeout must be between {MIN_TIMEOUT_SECONDS:g} and {MAX_TIMEOUT_SECONDS:g} seconds."
            )
        return self


def get_settings() -> Settings:
    """Read settings each call so tests can change the environment."""
    return Settings()
