"""Strict provider messages, generation settings, and responses."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from crossmarket_agentgym.config.models import REQUIRED_AGENT_MODEL

_ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


class StrictProviderModel(BaseModel):
    """Reject unknown fields and runtime mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ToolCall(StrictProviderModel):
    """One model-requested tool invocation with parsed arguments."""

    id: str = Field(min_length=1)
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(StrictProviderModel):
    """Provider-neutral chat message."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()

    @model_validator(mode="after")
    def validate_tool_message(self) -> Message:
        """Require tool identity only where the chat protocol allows it."""
        if self.role == "tool" and self.tool_call_id is None:
            raise ValueError("tool messages require tool_call_id")
        if self.role != "assistant" and self.tool_calls:
            raise ValueError("only assistant messages may contain tool calls")
        return self


class GenerationConfig(StrictProviderModel):
    """Auditable request-time generation and retry limits."""

    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=131_072)
    timeout_seconds: float = Field(default=120.0, gt=0.0, le=600.0)
    max_retries: int = Field(default=2, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=0.25, ge=0.0, le=30.0)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)


class ProviderConfig(StrictProviderModel):
    """Credential-free provider configuration."""

    provider: Literal["openai_compatible", "mock", "replay"] = "openai_compatible"
    model: str = REQUIRED_AGENT_MODEL
    api_key_env: str = "DEEPSEEK_API_KEY"
    base_url_env: str = "DEEPSEEK_BASE_URL"
    default_base_url: str = "https://api.deepseek.com"
    endpoint: str = "/chat/completions"
    structured_output_mode: Literal["json_object", "json_schema"] = "json_object"
    replay_path: str | None = None
    generation: GenerationConfig = Field(default_factory=GenerationConfig)

    @field_validator("model")
    @classmethod
    def require_project_model(cls, value: str) -> str:
        """Enforce the project-wide DeepSeek model policy."""
        if value != REQUIRED_AGENT_MODEL:
            raise ValueError(f"model must be {REQUIRED_AGENT_MODEL!r}")
        return value

    @field_validator("api_key_env", "base_url_env")
    @classmethod
    def validate_environment_name(cls, value: str) -> str:
        """Store only environment-variable names, never credential values."""
        if _ENVIRONMENT_NAME.fullmatch(value) is None:
            raise ValueError("must be an uppercase environment-variable name")
        return value

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        """Keep requests on one configured relative API endpoint."""
        if not value.startswith("/") or "://" in value or ".." in value:
            raise ValueError("endpoint must be an absolute API path")
        return value

    @model_validator(mode="after")
    def validate_replay_path(self) -> ProviderConfig:
        """Require a journal path only for replay providers."""
        if self.provider == "replay" and not self.replay_path:
            raise ValueError("replay provider requires replay_path")
        if self.provider != "replay" and self.replay_path is not None:
            raise ValueError("replay_path is only valid for replay provider")
        return self


class TokenUsage(StrictProviderModel):
    """Normalized provider token accounting."""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)


class ProviderMetadata(StrictProviderModel):
    """Credential-free metadata persisted beside an Agent run."""

    provider: str
    model: str
    base_url: str | None = None
    request_id: str | None = None
    finish_reason: str | None = None
    attempts: int = Field(default=1, ge=1)
    latency_seconds: float = Field(default=0.0, ge=0.0)
    request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    structured: bool = False
    replayed: bool = False


class LLMResponse(StrictProviderModel):
    """Provider-neutral response with validated structured data."""

    content: str
    structured_data: dict[str, Any] | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    usage: TokenUsage = Field(default_factory=TokenUsage)
    metadata: ProviderMetadata


class ProviderError(RuntimeError):
    """Safe provider failure carrying a stable code but no response body."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ProviderConfigurationError(ProviderError):
    """Missing or invalid provider configuration."""


class StructuredOutputError(ProviderError):
    """Model content did not satisfy the requested response schema."""
