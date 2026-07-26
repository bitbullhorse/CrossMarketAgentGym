"""Strict Phase 7 three-layer configuration and preset validation."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Literal, cast

import yaml
from pydantic import Field, field_validator, model_validator

from crossmarket_agentgym.agents.directives import (
    Cadence,
    HierarchicalDirective,
    ResearchMode,
    RiskContext,
    RiskDirective,
    RiskMode,
    StrictDirectiveModel,
)
from crossmarket_agentgym.agents.models import TeamSpec
from crossmarket_agentgym.data.schemas import Market
from crossmarket_agentgym.environments.config import EnvironmentConfig

LayerPreset = Literal[
    "no_llm",
    "research_only",
    "risk_only",
    "hierarchical_only",
    "research_plus_risk",
    "full_stack",
    "custom",
]

_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_PRESET_LAYERS: dict[str, tuple[bool, bool, bool]] = {
    "no_llm": (False, False, False),
    "research_only": (True, False, False),
    "risk_only": (False, True, False),
    "hierarchical_only": (False, False, True),
    "research_plus_risk": (True, True, False),
    "full_stack": (True, True, True),
}


def _validate_layer_team(
    team: TeamSpec | None,
    *,
    enabled: bool,
    required_type: str,
    directive_schema: str,
) -> None:
    if not enabled:
        if team is not None:
            raise ValueError("disabled LLM layer cannot retain a team")
        return
    if team is None:
        raise ValueError("enabled LLM layer requires a team")
    primary = [
        agent
        for agent in team.agents
        if agent.enabled and agent.type == required_type
    ]
    if not primary:
        raise ValueError(f"layer requires an enabled {required_type} Agent")
    if any(
        agent.metadata.get("directive_schema") != directive_schema
        for agent in primary
    ):
        raise ValueError(
            f"{required_type} requires metadata.directive_schema={directive_schema!r}"
        )


class ResearchLayerConfig(StrictDirectiveModel):
    """First-layer enable switch and authority mode."""

    enabled: bool = False
    mode: ResearchMode = "plan_only"
    team: TeamSpec | None = None

    @model_validator(mode="after")
    def validate_team(self) -> ResearchLayerConfig:
        _validate_layer_team(
            self.team,
            enabled=self.enabled,
            required_type="research_coordinator",
            directive_schema="research",
        )
        if self.enabled and self.team is not None:
            if self.mode == "plan_only" and any(
                agent.tools for agent in self.team.agents if agent.enabled
            ):
                raise ValueError("plan_only research cannot expose executable tools")
            if self.mode == "dry_run" and any(
                permission in {"write", "expensive"}
                for agent in self.team.agents
                if agent.enabled
                for permission in agent.allowed_permissions
            ):
                raise ValueError("dry_run research cannot grant write/expensive permission")
            if self.mode == "execute":
                for agent in self.team.agents:
                    if not agent.enabled:
                        continue
                    expensive = {"train_rl", "tune_rl"} & set(agent.tools)
                    if expensive and (
                        "estimate_compute_budget" not in agent.tools
                        or "expensive" not in agent.allowed_permissions
                        or agent.max_expensive_tool_calls < 1
                    ):
                        raise ValueError(
                            "execute research requires budget estimation and an "
                            "explicit expensive-tool budget"
                        )
        return self


class RiskLayerConfig(StrictDirectiveModel):
    """Second-layer advice/enforcement mode and deterministic cadence."""

    enabled: bool = False
    mode: RiskMode = "enforced"
    cadence: Cadence = "weekly"
    team: TeamSpec | None = None
    previous_directive: RiskDirective | None = None

    @model_validator(mode="after")
    def validate_team(self) -> RiskLayerConfig:
        _validate_layer_team(
            self.team,
            enabled=self.enabled,
            required_type="risk_manager",
            directive_schema="risk",
        )
        if self.enabled and self.team is not None:
            risk_count = sum(
                agent.count
                for agent in self.team.agents
                if agent.enabled and agent.type == "risk_manager"
            )
            if risk_count > 1 and self.team.conflict_policy != "most_conservative":
                raise ValueError(
                    "multi-Agent risk layer requires most_conservative conflict policy"
                )
        return self


class HierarchicalLayerConfig(StrictDirectiveModel):
    """Third-layer constraint-only fusion and deterministic cadence."""

    enabled: bool = False
    fusion: Literal["constraint"] = "constraint"
    cadence: Cadence = "monthly"
    team: TeamSpec | None = None
    previous_directive: HierarchicalDirective | None = None

    @model_validator(mode="after")
    def validate_team(self) -> HierarchicalLayerConfig:
        _validate_layer_team(
            self.team,
            enabled=self.enabled,
            required_type="market_regime",
            directive_schema="hierarchical",
        )
        return self


class LLMLayersConfig(StrictDirectiveModel):
    """Three independently switchable layers."""

    research: ResearchLayerConfig = Field(default_factory=ResearchLayerConfig)
    risk: RiskLayerConfig = Field(default_factory=RiskLayerConfig)
    hierarchical: HierarchicalLayerConfig = Field(
        default_factory=HierarchicalLayerConfig
    )


class Phase7RunConfig(StrictDirectiveModel):
    """Complete CPU-first three-layer fusion acceptance configuration."""

    run_id: str = "phase7-full-stack-offline"
    workspace_root: Path = Field(default=cast(Path, "."), validate_default=True)
    output_dir: Path = Field(default=cast(Path, "runs"), validate_default=True)
    prompt_version: str = Field(default="phase7.v1", min_length=1)
    seed: int = Field(default=1024, ge=0, le=2**32 - 1)
    load_entry_points: bool = True
    preset: LayerPreset
    objective: str = Field(min_length=1)
    research_payload: dict[str, Any] = Field(default_factory=dict)
    risk_context: RiskContext | None = None
    hierarchical_features: dict[str, float] = Field(default_factory=dict)
    as_of_index: int = Field(default=0, ge=0)
    layers: LLMLayersConfig
    administrator_environment: EnvironmentConfig = Field(
        default_factory=EnvironmentConfig
    )
    market_membership: tuple[Market, ...]
    raw_action: tuple[float, ...]
    current_weights: tuple[float, ...]
    tradable_mask: tuple[bool, ...]
    verify_directive_replay: bool = True

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        if _RUN_ID.fullmatch(value) is None:
            raise ValueError("run_id contains unsupported path characters")
        return value

    @model_validator(mode="after")
    def validate_stack(self) -> Phase7RunConfig:
        enabled = (
            self.layers.research.enabled,
            self.layers.risk.enabled,
            self.layers.hierarchical.enabled,
        )
        if self.preset != "custom" and enabled != _PRESET_LAYERS[self.preset]:
            raise ValueError(f"enabled layers do not match preset {self.preset!r}")
        if self.layers.risk.enabled and self.risk_context is None:
            raise ValueError("enabled risk layer requires risk_context")
        asset_count = len(self.market_membership)
        if asset_count < 1:
            raise ValueError("market_membership requires at least one asset")
        if len(self.raw_action) != asset_count + 1:
            raise ValueError("raw_action length must equal asset count plus cash")
        if len(self.current_weights) != asset_count + 1:
            raise ValueError("current_weights length must equal asset count plus cash")
        if len(self.tradable_mask) != asset_count:
            raise ValueError("tradable_mask length must equal asset count")
        if not math.isclose(math.fsum(self.current_weights), 1.0, abs_tol=1e-8):
            raise ValueError("current_weights must sum to one")
        return self


def load_phase7_run_config(path: Path) -> Phase7RunConfig:
    """Load strict YAML without resolving credentials or constructing Providers."""
    with path.open(encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("Phase 7 configuration must be a mapping")
    return Phase7RunConfig.model_validate(raw)
