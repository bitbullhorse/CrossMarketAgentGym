"""Phase 0 configuration boundary and immutable defaults."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
REQUIRED_AGENT_MODEL = "deepseek-v4-pro"


class StrictConfigModel(BaseModel):
    """Reject unknown keys and prevent runtime mutation of resolved configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectConfig(StrictConfigModel):
    """Reproducible project-level settings."""

    name: str = Field(default="crossmarket_agent_gym", min_length=1)
    seed: int = Field(default=1024, ge=0, le=2**32 - 1)
    output_dir: Path = Field(default=cast(Path, "runs"), validate_default=True)


class LLMConfig(StrictConfigModel):
    """Credential-free metadata for the required OpenAI-compatible provider."""

    provider: Literal["openai_compatible"] = "openai_compatible"
    model: str = REQUIRED_AGENT_MODEL
    api_key_env: str = "DEEPSEEK_API_KEY"
    base_url_env: str = "DEEPSEEK_BASE_URL"
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=131_072)
    timeout_seconds: int = Field(default=120, ge=1, le=600)
    max_retries: int = Field(default=2, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=0.25, ge=0.0, le=30.0)
    structured_output_mode: Literal["json_object", "json_schema"] = "json_object"

    @field_validator("model")
    @classmethod
    def require_project_model(cls, value: str) -> str:
        """Enforce the user-selected model policy for every project agent."""
        if value != REQUIRED_AGENT_MODEL:
            message = f"model must be {REQUIRED_AGENT_MODEL!r}"
            raise ValueError(message)
        return value

    @field_validator("api_key_env", "base_url_env")
    @classmethod
    def validate_environment_name(cls, value: str) -> str:
        """Accept environment-variable names but never credential values."""
        if _ENVIRONMENT_NAME.fullmatch(value) is None:
            raise ValueError("must be an uppercase environment-variable name")
        return value


class RootConfig(StrictConfigModel):
    """Minimal root configuration expanded in later phases."""

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
