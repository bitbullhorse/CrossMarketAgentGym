from __future__ import annotations

from crossmarket_agentgym.agents.aggregation import aggregate_results
from crossmarket_agentgym.agents.models import (
    AgentDecision,
    AgentExecutionResult,
    DecisionConstraints,
)


def _result(
    instance_id: str,
    decision: str,
    *,
    weight: float = 1.0,
    cash: float | None = None,
    asset: float | None = None,
    turnover: float | None = None,
    allow: bool | None = None,
) -> AgentExecutionResult:
    return AgentExecutionResult(
        invocation_id=f"{instance_id}.r1.i1",
        instance_id=instance_id,
        role_type="risk_manager",
        base_name=instance_id,
        seed=1,
        round_index=1,
        weight=weight,
        status="succeeded",
        attempts=1,
        duration_seconds=0.0,
        decision=AgentDecision(
            decision=decision,  # type: ignore[arg-type]
            summary=instance_id,
            confidence=0.8,
            risk_score=0.5,
            constraints=DecisionConstraints(
                cash_floor=cash,
                max_asset_weight=asset,
                max_market_weights={"US": asset} if asset is not None else {},
                max_turnover=turnover,
                allow_new_positions=allow,
            ),
        ),
    )


def test_most_conservative_intersects_structured_limits() -> None:
    aggregate = aggregate_results(
        [
            _result(
                "risk_0",
                "approve",
                cash=0.1,
                asset=0.4,
                turnover=0.8,
                allow=True,
            ),
            _result(
                "risk_1",
                "revise",
                cash=0.3,
                asset=0.2,
                turnover=0.25,
                allow=False,
            ),
        ],
        policy="most_conservative",
        quorum=0.5,
        expected_instances=["risk_0", "risk_1"],
    )
    assert aggregate.status == "resolved"
    assert aggregate.decision.decision == "revise"
    assert aggregate.decision.constraints.cash_floor == 0.3
    assert aggregate.decision.constraints.max_asset_weight == 0.2
    assert aggregate.decision.constraints.max_market_weights == {"US": 0.2}
    assert aggregate.decision.constraints.max_turnover == 0.25
    assert aggregate.decision.constraints.allow_new_positions is False
    assert aggregate.configured_conflict_policy == "most_conservative"
    assert aggregate.conflict_detected is True
    assert aggregate.aggregate_decision == "revise"
    assert aggregate.selected_directive_confidence == 0.8
    assert aggregate.committee_confidence == 0.8
    assert aggregate.confidence_aggregation == "minimum"


def test_weighted_vote_and_conservative_tie_break_are_structured() -> None:
    weighted = aggregate_results(
        [
            _result("a", "approve", weight=3.0),
            _result("b", "reject", weight=1.0),
        ],
        policy="weighted_vote",
        quorum=1.0,
        expected_instances=["a", "b"],
    )
    tied = aggregate_results(
        [_result("a", "approve"), _result("b", "reject")],
        policy="majority_vote",
        quorum=1.0,
        expected_instances=["a", "b"],
    )
    assert weighted.decision.decision == "approve"
    assert tied.decision.decision == "reject"


def test_no_quorum_and_reject_on_disagreement_fail_closed() -> None:
    no_quorum = aggregate_results(
        [_result("a", "approve")],
        policy="majority_vote",
        quorum=0.75,
        expected_instances=["a", "b"],
    )
    conflict = aggregate_results(
        [_result("a", "approve"), _result("b", "revise")],
        policy="reject",
        quorum=1.0,
        expected_instances=["a", "b"],
    )
    assert no_quorum.status == "no_quorum"
    assert no_quorum.decision.decision == "reject"
    assert no_quorum.failed_instances == ("b",)
    assert conflict.status == "rejected"
    assert conflict.configured_conflict_policy == "reject"
    assert conflict.conflict_detected is True
    assert conflict.aggregate_decision == "reject"


def test_reject_policy_without_conflict_can_approve() -> None:
    aggregate = aggregate_results(
        [_result("a", "approve"), _result("b", "approve")],
        policy="reject",
        quorum=1.0,
        expected_instances=["a", "b"],
    )

    assert aggregate.configured_conflict_policy == "reject"
    assert aggregate.conflict_detected is False
    assert aggregate.aggregate_decision == "approve"
    assert aggregate.status == "resolved"


def test_judge_policy_selects_only_configured_judge_decision() -> None:
    aggregate = aggregate_results(
        [_result("worker", "approve"), _result("judge", "revise")],
        policy="judge",
        quorum=1.0,
        expected_instances=["worker", "judge"],
        judge_instance="judge",
    )
    assert aggregate.decision.summary == "judge"
