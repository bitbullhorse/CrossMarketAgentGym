"""Strict configuration and result models for the unified Agent runtime."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from crossmarket_agentgym.agents.providers import (
    GenerationConfig,
    MockTurn,
    ProviderConfig,
)
from crossmarket_agentgym.agents.tools import ToolPermission
from crossmarket_agentgym.config.models import REQUIRED_AGENT_MODEL

AgentTopology = Literal[
    "single",
    "pipeline",
    "supervisor_worker",
    "committee_vote",
    "debate_then_judge",
    "map_reduce",
]
ConflictPolicy = Literal[
    "weighted_vote",
    "majority_vote",
    "judge",
    "most_conservative",
    "reject",
]
DecisionKind = Literal["approve", "revise", "reject", "abstain"]
AgentStatus = Literal["succeeded", "fallback", "failed", "timed_out"]

_SAFE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class StrictAgentModel(BaseModel):
    """Reject unknown fields and prevent mutation of resolved runtime state."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DecisionConstraints(StrictAgentModel):
    """Optional structured limits that conservative arbitration can intersect."""

    cash_floor: float | None = Field(default=None, ge=0.0, le=1.0)
    max_asset_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    max_market_weights: dict[str, float] = Field(default_factory=dict)
    max_turnover: float | None = Field(default=None, ge=0.0, le=2.0)
    allow_new_positions: bool | None = None

    @field_validator("max_market_weights")
    @classmethod
    def validate_market_weights(cls, value: dict[str, float]) -> dict[str, float]:
        """Keep every proposed market limit inside a normalized budget."""
        if any(not 0.0 <= weight <= 1.0 for weight in value.values()):
            raise ValueError("max_market_weights values must be between 0 and 1")
        return value


class AgentDecision(StrictAgentModel):
    """Provider-neutral structured envelope used by every Phase 6 role."""

    decision: DecisionKind
    summary: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_score: float = Field(default=1.0, ge=0.0, le=1.0)
    constraints: DecisionConstraints = Field(default_factory=DecisionConstraints)
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentSpec(StrictAgentModel):
    """One configurable Agent role, expanded into ``count`` independent instances."""

    type: str
    name: str
    count: int = Field(default=1, ge=1, le=32)
    provider: Literal["openai_compatible", "mock", "replay"] = "openai_compatible"
    model: str = REQUIRED_AGENT_MODEL
    prompt_template: str | None = None
    tools: tuple[str, ...] = ()
    weight: float = Field(default=1.0, gt=0.0)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=131_072)
    timeout_seconds: float = Field(default=120.0, gt=0.0, le=600.0)
    max_retries: int = Field(default=2, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=0.25, ge=0.0, le=30.0)
    max_tool_rounds: int = Field(default=3, ge=1, le=10)
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    fallback: AgentDecision | None = None
    allowed_permissions: frozenset[ToolPermission] = frozenset({"read", "compute"})
    max_tool_calls: int = Field(default=20, ge=0)
    max_expensive_tool_calls: int = Field(default=0, ge=0)
    max_tool_seconds: float = Field(default=300.0, ge=0.0)
    require_budget_before_expensive: bool = True
    api_key_env: str = "DEEPSEEK_API_KEY"
    base_url_env: str = "DEEPSEEK_BASE_URL"
    default_base_url: str = "https://api.deepseek.com"
    endpoint: str = "/chat/completions"
    structured_output_mode: Literal["json_object", "json_schema"] = "json_object"
    replay_path: str | None = None
    mock_scripts: tuple[tuple[MockTurn, ...], ...] = ()

    @field_validator("type", "name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Use stable portable identifiers for configuration and audit paths."""
        if _SAFE_NAME.fullmatch(value) is None:
            raise ValueError("must be a portable Agent identifier")
        return value

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Apply the project-wide model policy to every Agent."""
        if value != REQUIRED_AGENT_MODEL:
            raise ValueError(f"model must be {REQUIRED_AGENT_MODEL!r}")
        return value

    @field_validator("tools")
    @classmethod
    def validate_tools(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject ambiguous duplicate or malformed capability names."""
        if len(set(value)) != len(value):
            raise ValueError("tools must not contain duplicates")
        if any(_SAFE_NAME.fullmatch(name) is None for name in value):
            raise ValueError("tool names must be portable identifiers")
        return value

    @model_validator(mode="after")
    def validate_provider_fields(self) -> AgentSpec:
        """Keep offline scripts and replay paths explicit and provider-specific."""
        if self.provider == "mock":
            if not self.mock_scripts:
                raise ValueError("mock Agent requires mock_scripts")
            if len(self.mock_scripts) not in {1, self.count}:
                raise ValueError("mock_scripts must contain one script or one per instance")
        elif self.mock_scripts:
            raise ValueError("mock_scripts are only valid for mock Agents")
        if self.provider == "replay" and self.replay_path is None:
            raise ValueError("replay Agent requires replay_path")
        if self.provider != "replay" and self.replay_path is not None:
            raise ValueError("replay_path is only valid for replay Agents")
        return self

    def generation_config(self, seed: int) -> GenerationConfig:
        """Resolve auditable per-instance generation settings."""
        return GenerationConfig(
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
            retry_backoff_seconds=self.retry_backoff_seconds,
            seed=seed,
        )

    def provider_config(self, instance_id: str, seed: int) -> ProviderConfig:
        """Resolve one credential-free Provider configuration."""
        replay_path = (
            self.replay_path.replace("{instance_id}", instance_id)
            if self.replay_path is not None
            else None
        )
        return ProviderConfig(
            provider=self.provider,
            model=self.model,
            api_key_env=self.api_key_env,
            base_url_env=self.base_url_env,
            default_base_url=self.default_base_url,
            endpoint=self.endpoint,
            structured_output_mode=self.structured_output_mode,
            replay_path=replay_path,
            generation=self.generation_config(seed),
        )

    def mock_script(self, index: int) -> tuple[MockTurn, ...] | None:
        """Select an independent script for one expanded mock instance."""
        if self.provider != "mock":
            return None
        return self.mock_scripts[0 if len(self.mock_scripts) == 1 else index]


class TeamSpec(StrictAgentModel):
    """Communication topology and deterministic arbitration policy."""

    topology: AgentTopology
    agents: tuple[AgentSpec, ...]
    supervisor: str | None = None
    judge: str | None = None
    max_rounds: int = Field(default=3, ge=1, le=10)
    quorum: float = Field(default=0.5, gt=0.0, le=1.0)
    conflict_policy: ConflictPolicy = "most_conservative"
    parallel: bool = True
    max_workers: int = Field(default=8, ge=1, le=32)

    @model_validator(mode="after")
    def validate_topology(self) -> TeamSpec:
        """Resolve role references and reject impossible team structures early."""
        if not self.agents:
            raise ValueError("team requires at least one AgentSpec")
        names = [agent.name for agent in self.agents]
        if len(set(names)) != len(names):
            raise ValueError("AgentSpec names must be unique")
        enabled = [agent for agent in self.agents if agent.enabled]
        if not enabled:
            raise ValueError("team requires at least one enabled Agent")
        if sum(agent.count for agent in enabled) > 128:
            raise ValueError("team expands to more than 128 Agent instances")
        enabled_by_name = {agent.name: agent for agent in enabled}
        if self.topology == "single" and sum(agent.count for agent in enabled) != 1:
            raise ValueError("single topology requires exactly one enabled instance")
        if self.topology in {"supervisor_worker", "map_reduce"}:
            if self.supervisor not in enabled_by_name:
                raise ValueError(f"{self.topology} requires an enabled supervisor")
            if enabled_by_name[self.supervisor].count != 1:
                raise ValueError("supervisor must expand to exactly one instance")
            if sum(agent.count for agent in enabled) < 2:
                raise ValueError(f"{self.topology} requires at least one worker")
        if self.topology in {"debate_then_judge", "map_reduce"} and self.max_rounds < 2:
            raise ValueError(f"{self.topology} requires max_rounds >= 2")
        if self.topology == "debate_then_judge":
            if self.judge not in enabled_by_name:
                raise ValueError("debate_then_judge requires an enabled judge")
            if enabled_by_name[self.judge].count != 1:
                raise ValueError("judge must expand to exactly one instance")
            if sum(agent.count for agent in enabled) < 2:
                raise ValueError("debate_then_judge requires at least one debater")
        if self.conflict_policy == "judge":
            if self.judge not in enabled_by_name:
                raise ValueError("judge conflict policy requires an enabled judge")
            if enabled_by_name[self.judge].count != 1:
                raise ValueError("judge must expand to exactly one instance")
        return self


class AgentInstance(StrictAgentModel):
    """One expanded Agent with independent identity, seed, state, and limits."""

    instance_id: str
    index: int = Field(ge=0)
    seed: int = Field(ge=0, le=2**32 - 1)
    spec: AgentSpec


class UpstreamDecision(StrictAgentModel):
    """A structured message passed across topology edges."""

    invocation_id: str
    instance_id: str
    role_type: str
    status: AgentStatus
    decision: AgentDecision | None


class AgentContext(StrictAgentModel):
    """Immutable input to one role invocation."""

    run_id: str
    objective: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    round_index: int = Field(ge=1)
    upstream: tuple[UpstreamDecision, ...] = ()


class RoleInvocation(StrictAgentModel):
    """Normalized role return before runtime status and timing are attached."""

    decision: AgentDecision
    used_fallback: bool = False
    error_code: str | None = None


class AgentExecutionResult(StrictAgentModel):
    """Auditable outcome of one invocation, including partial failures."""

    invocation_id: str
    instance_id: str
    role_type: str
    base_name: str
    seed: int
    round_index: int
    weight: float
    status: AgentStatus
    attempts: int = Field(ge=1)
    duration_seconds: float = Field(ge=0.0)
    decision: AgentDecision | None = None
    error_code: str | None = None
    error_message: str | None = None

    def upstream(self) -> UpstreamDecision:
        """Create the bounded topology message exposed to later Agents."""
        return UpstreamDecision(
            invocation_id=self.invocation_id,
            instance_id=self.instance_id,
            role_type=self.role_type,
            status=self.status,
            decision=self.decision,
        )


class TeamAggregate(StrictAgentModel):
    """Deterministic structured team resolution."""

    status: Literal["resolved", "rejected", "no_quorum"]
    policy: ConflictPolicy
    decision: AgentDecision
    participants: tuple[str, ...]
    failed_instances: tuple[str, ...] = ()


class TeamRunResult(StrictAgentModel):
    """Serializable result shared by single-Agent and multi-Agent runs."""

    run_id: str
    topology: AgentTopology
    configured_instances: int = Field(ge=1)
    invocations: int = Field(ge=1)
    succeeded: int = Field(ge=0)
    fallback: int = Field(ge=0)
    failed: int = Field(ge=0)
    timed_out: int = Field(ge=0)
    rounds: int = Field(ge=1)
    parallel: bool
    network_used: bool
    results: tuple[AgentExecutionResult, ...]
    aggregate: TeamAggregate


class AgentRuntimeConfig(StrictAgentModel):
    """Complete credential-free Phase 6 CLI configuration."""

    run_id: str = "phase6-runtime-offline"
    workspace_root: Path = Path(".")
    output_dir: Path = Path("runs")
    prompt_version: str = Field(default="phase6.v1", min_length=1)
    seed: int = Field(default=1024, ge=0, le=2**32 - 1)
    objective: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    load_entry_points: bool = True
    team: TeamSpec

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        """Keep runtime paths local and portable."""
        if _RUN_ID.fullmatch(value) is None:
            raise ValueError("run_id contains unsupported path characters")
        return value
