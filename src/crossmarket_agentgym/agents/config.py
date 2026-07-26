"""Strict Phase 5 provider/tool acceptance configuration."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import Field, field_validator, model_validator

from crossmarket_agentgym.agents.models import AgentRuntimeConfig
from crossmarket_agentgym.agents.providers import (
    Message,
    MockTurn,
    ProviderConfig,
)
from crossmarket_agentgym.agents.providers.models import StrictProviderModel
from crossmarket_agentgym.agents.tools import ToolPolicy

_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class ProviderCheckOutput(StrictProviderModel):
    """Structured output used by the offline acceptance conversation."""

    status: str
    markets: tuple[str, ...]
    safe_to_continue: bool


class ProviderCheckConfig(StrictProviderModel):
    """Complete bounded provider/tool-loop configuration."""

    run_id: str = "phase5-provider-offline"
    workspace_root: Path = Field(default=cast(Path, "."), validate_default=True)
    output_dir: Path = Field(default=cast(Path, "runs"), validate_default=True)
    prompt_version: str = Field(default="phase5.v1", min_length=1)
    max_rounds: int = Field(default=3, ge=1, le=10)
    provider: ProviderConfig = Field(
        default_factory=lambda: ProviderConfig(provider="mock")
    )
    messages: tuple[Message, ...]
    tool_names: tuple[str, ...] = ("inspect_dataset",)
    tool_policy: ToolPolicy = Field(
        default_factory=lambda: ToolPolicy(
            allowed_permissions=frozenset({"read"}),
            allowed_tools=frozenset({"inspect_dataset"}),
        )
    )
    mock_script: tuple[MockTurn, ...] = ()
    fallback: ProviderCheckOutput = Field(
        default_factory=lambda: ProviderCheckOutput(
            status="safe_default",
            markets=(),
            safe_to_continue=False,
        )
    )
    verify_replay: bool = True

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        """Keep run paths local and portable."""
        if _RUN_ID.fullmatch(value) is None:
            raise ValueError("run_id contains unsupported path characters")
        return value

    @model_validator(mode="after")
    def validate_provider_inputs(self) -> ProviderCheckConfig:
        """Require scripts only for mock mode."""
        if self.provider.provider == "mock" and not self.mock_script:
            raise ValueError("mock provider check requires mock_script")
        if self.provider.provider != "mock" and self.mock_script:
            raise ValueError("mock_script is only valid for mock provider")
        return self


def load_provider_check_config(path: Path) -> ProviderCheckConfig:
    """Load a strict credential-free provider check YAML."""
    with path.open(encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("provider check configuration must be a mapping")
    return ProviderCheckConfig.model_validate(raw)


def load_agent_runtime_config(path: Path) -> AgentRuntimeConfig:
    """Load a strict credential-free single/multi-Agent YAML configuration."""
    with path.open(encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("Agent runtime configuration must be a mapping")
    return AgentRuntimeConfig.model_validate(raw)
