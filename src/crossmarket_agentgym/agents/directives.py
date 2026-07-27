"""Typed Phase 7 research, risk, and hierarchical directives."""

from __future__ import annotations

import math
import re
from typing import Any, Literal, cast

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from crossmarket_agentgym.data.schemas import Market
from crossmarket_agentgym.environments.config import EnvironmentConfig
from crossmarket_agentgym.environments.projection import ConstraintProjector

ResearchMode = Literal["plan_only", "dry_run", "execute"]
ResearchAction = Literal[
    "inspect_dataset",
    "validate_dataset",
    "list_markets",
    "list_symbols",
    "create_split",
    "validate_experiment_config",
    "estimate_compute_budget",
    "train_rl",
    "tune_rl",
    "evaluate_checkpoint",
    "compare_runs",
    "generate_report",
]
RiskMode = Literal["advisory", "enforced"]
Cadence = Literal["daily", "weekly", "monthly"]
MarketRegime = Literal[
    "risk_on",
    "neutral",
    "risk_off",
    "high_volatility",
    "unknown",
]

_STEP_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_CADENCE_ORDER = {"daily": 0, "weekly": 1, "monthly": 2}
_VALID_MARKETS = frozenset({"CN", "HK", "JP", "US"})


def _market(value: str) -> Market:
    if value not in _VALID_MARKETS:
        raise ValueError(f"unknown market in Agent directive: {value}")
    return cast(Market, value)


class StrictDirectiveModel(BaseModel):
    """Reject unknown keys, mutation, and non-finite numerical instructions."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


def _contains_test_access(value: Any, *, key: str = "") -> bool:
    if isinstance(value, dict):
        return any(
            _contains_test_access(item, key=str(nested_key))
            for nested_key, item in value.items()
        )
    if isinstance(value, list | tuple):
        return any(_contains_test_access(item, key=key) for item in value)
    key_lower = key.lower()
    if key_lower in {"partition", "data_partition", "dataset_partition"}:
        return isinstance(value, str) and value.lower() == "test"
    return "test_metric" in key_lower


class ResearchStep(StrictDirectiveModel):
    """One schema-validated research action; execution still requires a registered tool."""

    id: str
    action: ResearchAction
    arguments: dict[str, Any] = Field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    expected_artifacts: tuple[str, ...] = ()

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if _STEP_ID.fullmatch(value) is None:
            raise ValueError("research step id must be portable")
        return value

    @model_validator(mode="after")
    def reject_test_access(self) -> ResearchStep:
        """Research and tuning steps cannot request the hidden test partition."""
        if _contains_test_access(self.arguments):
            raise ValueError("research step cannot access test data or test metrics")
        return self


class ResearchDirective(StrictDirectiveModel):
    """First-layer plan or bounded execution directive."""

    objective: str = Field(min_length=1, max_length=4000)
    mode: ResearchMode
    steps: tuple[ResearchStep, ...] = ()
    validation_only: Literal[True] = True
    test_metrics_accessed: Literal[False] = False
    safe_to_execute: bool = False
    estimated_compute_units: float = Field(default=0.0, ge=0.0)
    rationale: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_plan(self) -> ResearchDirective:
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("research step ids must be unique")
        seen: set[str] = set()
        for step in self.steps:
            if any(dependency not in seen for dependency in step.depends_on):
                raise ValueError("research dependencies must reference an earlier step")
            seen.add(step.id)
        if self.mode != "execute" and self.safe_to_execute:
            raise ValueError("only execute mode may set safe_to_execute")
        return self


def static_research_fallback(mode: ResearchMode, objective: str) -> ResearchDirective:
    """Return a no-action administrator fallback."""
    return ResearchDirective(
        objective=objective,
        mode=mode,
        steps=(),
        safe_to_execute=False,
        rationale="Static research fallback schedules no tools or experiments.",
        confidence=0.0,
    )


class RiskContext(StrictDirectiveModel):
    """Structured portfolio evidence visible to the risk layer."""

    portfolio_value: float = Field(gt=0.0)
    current_drawdown: float = Field(ge=0.0, le=1.0)
    rolling_volatility: float = Field(ge=0.0)
    rolling_cvar: float = Field(ge=0.0)
    turnover: float = Field(ge=0.0, le=2.0)
    market_exposures: dict[str, float] = Field(default_factory=dict)
    asset_exposures: dict[str, float] = Field(default_factory=dict)
    liquidity_flags: dict[str, bool] = Field(default_factory=dict)
    regime_features: dict[str, float] = Field(default_factory=dict)

    @field_validator("market_exposures", "asset_exposures")
    @classmethod
    def validate_exposures(cls, value: dict[str, float]) -> dict[str, float]:
        if any(abs(exposure) > 3.0 for exposure in value.values()):
            raise ValueError("exposure magnitude cannot exceed 3")
        return value


class RiskDirective(StrictDirectiveModel):
    """Second-layer bounded risk proposal."""

    risk_budget: float = Field(ge=0.0, le=1.0)
    max_asset_weight: float = Field(gt=0.0, le=1.0)
    max_market_weights: dict[str, float] = Field(default_factory=dict)
    cash_floor: float = Field(ge=0.0, le=1.0)
    max_turnover: float = Field(ge=0.0, le=2.0)
    allow_new_positions: bool
    rebalance_frequency: Cadence
    rationale: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("max_market_weights")
    @classmethod
    def validate_market_caps(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not 0.0 < cap <= 1.0 for cap in value.values()):
            raise ValueError("risk market caps must be in (0, 1]")
        return value


def static_risk_fallback(markets: tuple[str, ...]) -> RiskDirective:
    """Fail closed without using a zero value forbidden by the public schema."""
    return RiskDirective(
        risk_budget=0.0,
        max_asset_weight=1e-12,
        max_market_weights={market: 1e-12 for market in sorted(set(markets))},
        cash_floor=1.0,
        max_turnover=0.0,
        allow_new_positions=False,
        rebalance_frequency="monthly",
        rationale="Static risk fallback denies new exposure.",
        confidence=1.0,
    )


class AdministratorRiskPolicy(StrictDirectiveModel):
    """Immutable absolute risk limits owned outside every LLM."""

    max_risk_budget: float = Field(default=1.0, ge=0.0, le=1.0)
    max_asset_weight: float = Field(gt=0.0, le=1.0)
    default_max_market_weight: float = Field(gt=0.0, le=1.0)
    max_market_weights: dict[str, float] = Field(default_factory=dict)
    minimum_cash_floor: float = Field(ge=0.0, le=1.0)
    max_turnover: float = Field(ge=0.0, le=2.0)
    allow_new_positions: bool = True
    minimum_rebalance_interval: Cadence = "daily"

    @field_validator("max_market_weights")
    @classmethod
    def validate_overrides(cls, value: dict[str, float]) -> dict[str, float]:
        if any(not 0.0 < cap <= 1.0 for cap in value.values()):
            raise ValueError("administrator market caps must be in (0, 1]")
        return value

    @classmethod
    def from_environment(
        cls,
        environment: EnvironmentConfig,
    ) -> AdministratorRiskPolicy:
        """Derive the LLM-visible ceiling from deterministic environment limits."""
        return cls(
            max_risk_budget=min(1.0, environment.max_leverage),
            max_asset_weight=environment.max_asset_weight,
            default_max_market_weight=min(1.0, environment.max_market_weight),
            max_market_weights={
                str(market): min(1.0, cap)
                for market, cap in environment.market_weight_overrides.items()
            },
            minimum_cash_floor=environment.cash_floor,
            max_turnover=environment.max_turnover,
            allow_new_positions=True,
        )


class RiskMergeResult(StrictDirectiveModel):
    """Auditable proposed/effective risk directive and every clipped field."""

    mode: RiskMode
    proposed: RiskDirective | None
    effective: RiskDirective
    administrator_policy: AdministratorRiskPolicy
    clipped_fields: tuple[str, ...] = ()


def _administrator_risk_baseline(
    policy: AdministratorRiskPolicy,
    markets: tuple[str, ...],
) -> RiskDirective:
    market_caps = {
        market: policy.max_market_weights.get(
            market,
            policy.default_max_market_weight,
        )
        for market in sorted(set(markets))
    }
    return RiskDirective(
        risk_budget=policy.max_risk_budget,
        max_asset_weight=policy.max_asset_weight,
        max_market_weights=market_caps,
        cash_floor=policy.minimum_cash_floor,
        max_turnover=policy.max_turnover,
        allow_new_positions=policy.allow_new_positions,
        rebalance_frequency=policy.minimum_rebalance_interval,
        rationale="Administrator hard-policy baseline.",
        confidence=1.0,
    )


def merge_risk_directive(
    proposed: RiskDirective | None,
    *,
    policy: AdministratorRiskPolicy,
    markets: tuple[str, ...],
    mode: RiskMode,
) -> RiskMergeResult:
    """Intersect LLM advice with hard policy; advisory mode cannot change limits."""
    baseline = _administrator_risk_baseline(policy, markets)
    if proposed is None or mode == "advisory":
        return RiskMergeResult(
            mode=mode,
            proposed=proposed,
            effective=baseline,
            administrator_policy=policy,
            clipped_fields=("advisory_not_enforced",) if proposed is not None else (),
        )
    clipped: list[str] = []

    def bounded_min(name: str, candidate: float, ceiling: float) -> float:
        if candidate > ceiling:
            clipped.append(name)
        return min(candidate, ceiling)

    risk_budget = bounded_min(
        "risk_budget",
        proposed.risk_budget,
        policy.max_risk_budget,
    )
    max_asset = bounded_min(
        "max_asset_weight",
        proposed.max_asset_weight,
        policy.max_asset_weight,
    )
    cash_floor = max(proposed.cash_floor, policy.minimum_cash_floor)
    if proposed.cash_floor < policy.minimum_cash_floor:
        clipped.append("cash_floor")
    turnover = bounded_min(
        "max_turnover",
        proposed.max_turnover,
        policy.max_turnover,
    )
    allow_new = proposed.allow_new_positions and policy.allow_new_positions
    if proposed.allow_new_positions and not policy.allow_new_positions:
        clipped.append("allow_new_positions")
    frequency = max(
        proposed.rebalance_frequency,
        policy.minimum_rebalance_interval,
        key=lambda item: _CADENCE_ORDER[item],
    )
    if frequency != proposed.rebalance_frequency:
        clipped.append("rebalance_frequency")
    market_caps: dict[str, float] = {}
    all_markets = sorted(
        set(markets)
        | set(proposed.max_market_weights)
        | set(policy.max_market_weights)
    )
    for market in all_markets:
        hard_cap = policy.max_market_weights.get(
            market,
            policy.default_max_market_weight,
        )
        candidate = proposed.max_market_weights.get(market, hard_cap)
        market_caps[market] = min(candidate, hard_cap)
        if candidate > hard_cap:
            clipped.append(f"max_market_weights.{market}")
    effective = RiskDirective(
        risk_budget=risk_budget,
        max_asset_weight=max_asset,
        max_market_weights=market_caps,
        cash_floor=cash_floor,
        max_turnover=turnover,
        allow_new_positions=allow_new,
        rebalance_frequency=frequency,
        rationale="Administrator-intersected risk directive: " + proposed.rationale,
        confidence=proposed.confidence,
    )
    return RiskMergeResult(
        mode=mode,
        proposed=proposed,
        effective=effective,
        administrator_policy=policy,
        clipped_fields=tuple(dict.fromkeys(clipped)),
    )


class HierarchicalDirective(StrictDirectiveModel):
    """Third-layer low-frequency market and objective budget."""

    market_regime: MarketRegime
    market_budgets: dict[str, float] = Field(default_factory=dict)
    sector_budgets: dict[str, float] | None = None
    global_risk_budget: float = Field(ge=0.0, le=1.0)
    rebalance_interval: int = Field(ge=1, le=252)
    objective_weights: dict[str, float]
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("market_budgets", "sector_budgets")
    @classmethod
    def validate_budgets(
        cls,
        value: dict[str, float] | None,
    ) -> dict[str, float] | None:
        if value is not None and any(
            not 0.0 <= budget <= 1.0 for budget in value.values()
        ):
            raise ValueError("hierarchical budgets must be between 0 and 1")
        return value

    @field_validator("objective_weights")
    @classmethod
    def validate_objective_weights(
        cls,
        value: dict[str, float],
    ) -> dict[str, float]:
        if not value or any(weight < 0.0 for weight in value.values()):
            raise ValueError("objective_weights must be non-empty and non-negative")
        total = math.fsum(value.values())
        if not math.isclose(total, 1.0, abs_tol=1e-9):
            raise ValueError("objective_weights must sum to 1")
        return value


def static_hierarchical_fallback() -> HierarchicalDirective:
    """Return a capital-preservation directive when the strategy layer fails."""
    return HierarchicalDirective(
        market_regime="unknown",
        market_budgets={},
        sector_budgets=None,
        global_risk_budget=0.0,
        rebalance_interval=21,
        objective_weights={"capital_preservation": 1.0},
        confidence=0.0,
    )


class EffectiveConstraintSet(StrictDirectiveModel):
    """Resolved constraints supplied to the deterministic projector."""

    risk_budget: float = Field(ge=0.0, le=1.0)
    max_asset_weight: float = Field(gt=0.0, le=1.0)
    max_market_weights: dict[str, float]
    cash_floor: float = Field(ge=0.0, le=1.0)
    max_turnover: float = Field(ge=0.0, le=2.0)
    allow_new_positions: bool


class CashFloorDerivation(StrictDirectiveModel):
    """Auditable link from risk budget to the effective cash reserve."""

    field: Literal["cash_floor"] = "cash_floor"
    agent_value: float = Field(ge=0.0, le=1.0)
    risk_budget_implied_value: float = Field(ge=0.0, le=1.0)
    effective_value: float = Field(ge=0.0, le=1.0)
    operator: Literal["max"] = "max"
    reason: Literal["Invested capital cannot exceed risk budget."] = (
        "Invested capital cannot exceed risk budget."
    )


class ConstraintFusionResult(StrictDirectiveModel):
    """Proof that Agent budgets only tightened administrator constraints."""

    hard_environment: EnvironmentConfig
    effective_environment: EnvironmentConfig
    constraints: EffectiveConstraintSet
    risk: RiskMergeResult
    hierarchical: HierarchicalDirective | None
    cash_floor_derivation: CashFloorDerivation
    tightened_fields: tuple[str, ...]


def fuse_constraint_directives(
    *,
    environment: EnvironmentConfig,
    markets: tuple[Market, ...],
    risk: RiskMergeResult,
    hierarchical: HierarchicalDirective | None,
) -> ConstraintFusionResult:
    """Build a stricter immutable EnvironmentConfig; never widen hard limits."""
    if environment.allow_short:
        raise ValueError("Phase 7 constraint fusion currently requires long-only mode")
    market_names = tuple(str(market) for market in markets)
    effective_risk = risk.effective
    hierarchical_budget = (
        hierarchical.global_risk_budget if hierarchical is not None else 1.0
    )
    risk_budget = min(effective_risk.risk_budget, hierarchical_budget)
    agent_cash_floor = max(
        environment.cash_floor,
        effective_risk.cash_floor,
    )
    risk_budget_implied_cash_floor = 1.0 - risk_budget
    cash_floor = max(agent_cash_floor, risk_budget_implied_cash_floor)
    max_asset = max(
        1e-12,
        min(environment.max_asset_weight, effective_risk.max_asset_weight),
    )
    turnover = min(environment.max_turnover, effective_risk.max_turnover)
    all_market_names = sorted(
        set(market_names)
        | {str(market) for market in environment.market_weight_overrides}
        | set(effective_risk.max_market_weights)
        | (
            set(hierarchical.market_budgets)
            if hierarchical is not None
            else set()
        )
    )
    market_caps: dict[str, float] = {}
    for market in all_market_names:
        typed_market = _market(market)
        hard_cap = environment.market_weight_overrides.get(
            typed_market,
            environment.max_market_weight,
        )
        risk_cap = effective_risk.max_market_weights.get(market, hard_cap)
        hierarchical_cap = (
            hierarchical.market_budgets.get(market, hard_cap)
            if hierarchical is not None
            else hard_cap
        )
        market_caps[market] = max(
            1e-12,
            min(hard_cap, risk_cap, hierarchical_cap),
        )
    effective_environment = environment.model_copy(
        update={
            "max_asset_weight": max_asset,
            "market_weight_overrides": {
                _market(market): cap for market, cap in market_caps.items()
            },
            "cash_floor": cash_floor,
            "max_turnover": turnover,
        }
    )
    tightened: list[str] = []
    if max_asset < environment.max_asset_weight:
        tightened.append("max_asset_weight")
    if cash_floor > environment.cash_floor:
        tightened.append("cash_floor")
    if turnover < environment.max_turnover:
        tightened.append("max_turnover")
    for market, cap in market_caps.items():
        hard_cap = environment.market_weight_overrides.get(
            _market(market),
            environment.max_market_weight,
        )
        if cap < hard_cap:
            tightened.append(f"max_market_weights.{market}")
    if not effective_risk.allow_new_positions:
        tightened.append("allow_new_positions")
    return ConstraintFusionResult(
        hard_environment=environment,
        effective_environment=effective_environment,
        constraints=EffectiveConstraintSet(
            risk_budget=risk_budget,
            max_asset_weight=max_asset,
            max_market_weights=market_caps,
            cash_floor=cash_floor,
            max_turnover=turnover,
            allow_new_positions=effective_risk.allow_new_positions,
        ),
        risk=risk,
        hierarchical=hierarchical,
        cash_floor_derivation=CashFloorDerivation(
            agent_value=agent_cash_floor,
            risk_budget_implied_value=risk_budget_implied_cash_floor,
            effective_value=cash_floor,
        ),
        tightened_fields=tuple(dict.fromkeys(tightened)),
    )


class DirectiveProjection(StrictDirectiveModel):
    """Projected DRL action; this object contains no account mutation method."""

    raw_action: tuple[float, ...]
    normalized_weights: tuple[float, ...]
    projected_weights: tuple[float, ...]
    clipping_reasons: tuple[str, ...]
    unresolved_constraints: tuple[str, ...]
    dominant_projection_reason: str
    secondary_projection_reasons: tuple[str, ...]
    fusion: ConstraintFusionResult


def project_with_directives(
    raw_action: tuple[float, ...],
    *,
    current_weights: tuple[float, ...],
    tradable_mask: tuple[bool, ...],
    markets: tuple[Market, ...],
    fusion: ConstraintFusionResult,
) -> DirectiveProjection:
    """Apply Agent-derived tighter limits through the existing deterministic projector."""
    effective_tradable = np.asarray(tradable_mask, dtype=bool).copy()
    current = np.asarray(current_weights, dtype=np.float64)
    if not fusion.constraints.allow_new_positions:
        effective_tradable &= current[1:] > 1e-12
    projection = ConstraintProjector(
        fusion.effective_environment,
        markets,
    ).project(
        np.asarray(raw_action, dtype=np.float64),
        current_weights=current,
        tradable_mask=effective_tradable,
    )
    reasons = list(projection.clipping_reasons)
    reasons.extend(f"agent:{item}" for item in fusion.tightened_fields)
    all_cash = bool(np.all(current[1:] <= 1e-12))
    if not fusion.constraints.allow_new_positions and all_cash:
        dominant_reason = "no_new_positions_from_all_cash_state"
    elif not fusion.constraints.allow_new_positions:
        dominant_reason = "no_new_positions_existing_positions_only"
    elif projection.clipping_reasons:
        dominant_reason = projection.clipping_reasons[0]
    elif fusion.tightened_fields:
        dominant_reason = f"agent:{fusion.tightened_fields[0]}"
    else:
        dominant_reason = "no_projection_change"
    return DirectiveProjection(
        raw_action=tuple(float(item) for item in projection.raw_action),
        normalized_weights=tuple(
            float(item) for item in projection.normalized_weights
        ),
        projected_weights=tuple(
            float(item) for item in projection.projected_weights
        ),
        clipping_reasons=tuple(dict.fromkeys(reasons)),
        unresolved_constraints=projection.unresolved_constraints,
        dominant_projection_reason=dominant_reason,
        secondary_projection_reasons=(
            "max_asset_weight",
            "cash_floor",
            "max_turnover",
            "market_weight_limits",
        ),
        fusion=fusion,
    )


def cadence_due(cadence: Cadence, as_of_index: int) -> bool:
    """Use deterministic trading-session cadence without wall-clock dependence."""
    if as_of_index < 0:
        raise ValueError("as_of_index must be non-negative")
    interval = {"daily": 1, "weekly": 5, "monthly": 21}[cadence]
    return as_of_index % interval == 0
