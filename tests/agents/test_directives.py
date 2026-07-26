from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from crossmarket_agentgym.agents.directives import (
    AdministratorRiskPolicy,
    HierarchicalDirective,
    ResearchDirective,
    RiskDirective,
    cadence_due,
    fuse_constraint_directives,
    merge_risk_directive,
    project_with_directives,
    static_risk_fallback,
)
from crossmarket_agentgym.environments import EnvironmentConfig


def _environment() -> EnvironmentConfig:
    return EnvironmentConfig(
        max_asset_weight=0.20,
        max_market_weight=0.50,
        market_weight_overrides={"CN": 0.40, "US": 0.45},
        cash_floor=0.10,
        max_turnover=0.80,
    )


def _risk(**updates: object) -> RiskDirective:
    values: dict[str, object] = {
        "risk_budget": 0.8,
        "max_asset_weight": 0.3,
        "max_market_weights": {"CN": 0.6, "US": 0.7},
        "cash_floor": 0.05,
        "max_turnover": 1.5,
        "allow_new_positions": True,
        "rebalance_frequency": "daily",
        "rationale": "structured proposal",
        "confidence": 0.8,
    }
    values.update(updates)
    return RiskDirective.model_validate(values)


def _hierarchical(**updates: object) -> HierarchicalDirective:
    values: dict[str, object] = {
        "market_regime": "neutral",
        "market_budgets": {"CN": 0.30, "US": 0.25},
        "sector_budgets": None,
        "global_risk_budget": 0.60,
        "rebalance_interval": 21,
        "objective_weights": {"return": 0.5, "risk": 0.5},
        "confidence": 0.8,
    }
    values.update(updates)
    return HierarchicalDirective.model_validate(values)


def test_research_directive_rejects_test_access_and_unsafe_mode() -> None:
    with pytest.raises(ValidationError, match="test data"):
        ResearchDirective.model_validate(
            {
                "objective": "Tune",
                "mode": "execute",
                "steps": [
                    {
                        "id": "evaluate",
                        "action": "evaluate_checkpoint",
                        "arguments": {"partition": "test"},
                    }
                ],
                "safe_to_execute": True,
                "rationale": "bad",
            }
        )
    with pytest.raises(ValidationError, match="only execute"):
        ResearchDirective.model_validate(
            {
                "objective": "Plan",
                "mode": "plan_only",
                "safe_to_execute": True,
                "rationale": "bad",
            }
        )


def test_research_dependencies_must_be_unique_and_ordered() -> None:
    with pytest.raises(ValidationError, match="earlier step"):
        ResearchDirective.model_validate(
            {
                "objective": "Plan",
                "mode": "plan_only",
                "steps": [
                    {
                        "id": "train",
                        "action": "train_rl",
                        "depends_on": ["validate"],
                    }
                ],
                "rationale": "bad dependency",
            }
        )


def test_directive_schemas_reject_nonfinite_and_invalid_budgets() -> None:
    with pytest.raises(ValidationError):
        _risk(risk_budget=math.inf)
    with pytest.raises(ValidationError, match="sum to 1"):
        _hierarchical(objective_weights={"return": 0.8, "risk": 0.8})


def test_enforced_risk_can_only_tighten_administrator_policy() -> None:
    environment = _environment()
    policy = AdministratorRiskPolicy.from_environment(environment)
    result = merge_risk_directive(
        _risk(),
        policy=policy,
        markets=("CN", "US"),
        mode="enforced",
    )
    assert result.effective.risk_budget <= policy.max_risk_budget
    assert result.effective.max_asset_weight == environment.max_asset_weight
    assert result.effective.max_market_weights == {"CN": 0.4, "US": 0.45}
    assert result.effective.cash_floor == environment.cash_floor
    assert result.effective.max_turnover == environment.max_turnover
    assert {
        "max_asset_weight",
        "max_market_weights.CN",
        "max_market_weights.US",
        "cash_floor",
        "max_turnover",
    }.issubset(result.clipped_fields)


def test_advisory_risk_never_changes_effective_limits() -> None:
    environment = _environment()
    policy = AdministratorRiskPolicy.from_environment(environment)
    result = merge_risk_directive(
        static_risk_fallback(("CN", "US")),
        policy=policy,
        markets=("CN", "US"),
        mode="advisory",
    )
    assert result.effective.max_asset_weight == environment.max_asset_weight
    assert result.effective.cash_floor == environment.cash_floor
    assert result.effective.allow_new_positions is True
    assert result.clipped_fields == ("advisory_not_enforced",)


def test_hierarchical_and_risk_constraints_use_existing_projector() -> None:
    environment = _environment()
    merged = merge_risk_directive(
        _risk(
            risk_budget=0.7,
            max_asset_weight=0.15,
            max_market_weights={"CN": 0.35, "US": 0.30},
            cash_floor=0.2,
            max_turnover=0.4,
        ),
        policy=AdministratorRiskPolicy.from_environment(environment),
        markets=("CN", "US"),
        mode="enforced",
    )
    fusion = fuse_constraint_directives(
        environment=environment,
        markets=("CN", "US"),
        risk=merged,
        hierarchical=_hierarchical(),
    )
    assert fusion.constraints.risk_budget == 0.6
    assert fusion.constraints.cash_floor == 0.4
    assert fusion.constraints.max_asset_weight == 0.15
    assert fusion.constraints.max_market_weights == {"CN": 0.3, "US": 0.25}
    projection = project_with_directives(
        (0.0, 0.8, 0.8),
        current_weights=(1.0, 0.0, 0.0),
        tradable_mask=(True, True),
        markets=("CN", "US"),
        fusion=fusion,
    )
    assert math.isclose(sum(projection.projected_weights), 1.0, abs_tol=1e-9)
    assert projection.projected_weights[0] >= 0.4 - 1e-9
    assert projection.projected_weights[1] <= 0.15 + 1e-9
    assert projection.projected_weights[2] <= 0.15 + 1e-9
    assert any(reason.startswith("agent:") for reason in projection.clipping_reasons)


def test_failed_risk_agent_cannot_open_positions() -> None:
    environment = _environment()
    fallback = static_risk_fallback(("CN", "US"))
    merged = merge_risk_directive(
        fallback,
        policy=AdministratorRiskPolicy.from_environment(environment),
        markets=("CN", "US"),
        mode="enforced",
    )
    fusion = fuse_constraint_directives(
        environment=environment,
        markets=("CN", "US"),
        risk=merged,
        hierarchical=None,
    )
    projection = project_with_directives(
        (0.0, 1.0, 1.0),
        current_weights=(1.0, 0.0, 0.0),
        tradable_mask=(True, True),
        markets=("CN", "US"),
        fusion=fusion,
    )
    assert projection.projected_weights == (1.0, 0.0, 0.0)
    assert fusion.constraints.allow_new_positions is False


def test_constraint_fusion_rejects_short_mode_and_unknown_markets() -> None:
    environment = _environment()
    risk = merge_risk_directive(
        _risk(),
        policy=AdministratorRiskPolicy.from_environment(environment),
        markets=("CN",),
        mode="enforced",
    )
    with pytest.raises(ValueError, match="unknown market"):
        fuse_constraint_directives(
            environment=environment,
            markets=("CN",),
            risk=risk,
            hierarchical=_hierarchical(market_budgets={"XX": 0.2}),
        )
    short_environment = EnvironmentConfig(
        allow_short=True,
        max_leverage=1.5,
        max_asset_weight=0.2,
        max_market_weight=0.5,
    )
    with pytest.raises(ValueError, match="long-only"):
        fuse_constraint_directives(
            environment=short_environment,
            markets=("CN",),
            risk=merge_risk_directive(
                _risk(max_market_weights={"CN": 0.4}),
                policy=AdministratorRiskPolicy.from_environment(short_environment),
                markets=("CN",),
                mode="enforced",
            ),
            hierarchical=None,
        )


def test_cadence_is_session_index_deterministic() -> None:
    assert cadence_due("daily", 7)
    assert cadence_due("weekly", 10)
    assert not cadence_due("weekly", 11)
    assert cadence_due("monthly", 42)
    with pytest.raises(ValueError, match="non-negative"):
        cadence_due("daily", -1)
