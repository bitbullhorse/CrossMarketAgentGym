"""Deterministic structured conflict policies for Agent teams."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from crossmarket_agentgym.agents.models import (
    AgentDecision,
    AgentExecutionResult,
    ConflictPolicy,
    DecisionConstraints,
    TeamAggregate,
)

_CONSERVATIVE_ORDER = {
    "abstain": 0,
    "approve": 1,
    "revise": 2,
    "reject": 3,
}


def _latest_by_instance(
    results: Iterable[AgentExecutionResult],
) -> dict[str, AgentExecutionResult]:
    latest: dict[str, AgentExecutionResult] = {}
    for result in results:
        latest[result.instance_id] = result
    return latest


def _safe_rejection(summary: str) -> AgentDecision:
    return AgentDecision(
        decision="reject",
        summary=summary,
        confidence=1.0,
        risk_score=1.0,
        constraints=DecisionConstraints(
            cash_floor=1.0,
            max_asset_weight=0.0,
            max_turnover=0.0,
            allow_new_positions=False,
        ),
    )


def _combine_constraints(decisions: list[AgentDecision]) -> DecisionConstraints:
    cash = [
        item.constraints.cash_floor
        for item in decisions
        if item.constraints.cash_floor is not None
    ]
    asset = [
        item.constraints.max_asset_weight
        for item in decisions
        if item.constraints.max_asset_weight is not None
    ]
    turnover = [
        item.constraints.max_turnover
        for item in decisions
        if item.constraints.max_turnover is not None
    ]
    position_flags = [
        item.constraints.allow_new_positions
        for item in decisions
        if item.constraints.allow_new_positions is not None
    ]
    market_values: dict[str, list[float]] = defaultdict(list)
    for item in decisions:
        for market, limit in item.constraints.max_market_weights.items():
            market_values[market].append(limit)
    return DecisionConstraints(
        cash_floor=max(cash) if cash else None,
        max_asset_weight=min(asset) if asset else None,
        max_market_weights={
            market: min(values)
            for market, values in sorted(market_values.items())
        },
        max_turnover=min(turnover) if turnover else None,
        allow_new_positions=all(position_flags) if position_flags else None,
    )


def _most_conservative(
    candidates: list[AgentExecutionResult],
) -> AgentDecision:
    decisions = [item.decision for item in candidates if item.decision is not None]
    if not decisions:
        return _safe_rejection("No structured Agent decision was available.")
    eligible = [item for item in candidates if item.decision is not None]

    def conservative_key(item: AgentExecutionResult) -> tuple[int, float, str]:
        assert item.decision is not None
        return (
            _CONSERVATIVE_ORDER[item.decision.decision],
            item.decision.risk_score,
            item.instance_id,
        )

    selected_result = max(eligible, key=conservative_key)
    assert selected_result.decision is not None
    return AgentDecision(
        decision=selected_result.decision.decision,
        summary="Most-conservative structured arbitration: "
        + selected_result.decision.summary,
        confidence=min(item.confidence for item in decisions),
        risk_score=max(item.risk_score for item in decisions),
        constraints=_combine_constraints(decisions),
        payload=selected_result.decision.payload,
    )


def _vote(
    candidates: list[AgentExecutionResult],
    *,
    weighted: bool,
) -> AgentDecision:
    scores: dict[str, float] = defaultdict(float)
    for item in candidates:
        assert item.decision is not None
        contribution = item.weight if weighted else 1.0
        scores[item.decision.decision] += contribution
    winning_kind = max(
        scores,
        key=lambda kind: (scores[kind], _CONSERVATIVE_ORDER[kind]),
    )
    matching = [
        item
        for item in candidates
        if item.decision is not None and item.decision.decision == winning_kind
    ]
    selected = max(
        matching,
        key=_vote_candidate_key,
    )
    assert selected.decision is not None
    return selected.decision


def _vote_candidate_key(item: AgentExecutionResult) -> tuple[float, str]:
    assert item.decision is not None
    return (item.weight * item.decision.confidence, item.instance_id)


def aggregate_results(
    results: Iterable[AgentExecutionResult],
    *,
    policy: ConflictPolicy,
    quorum: float,
    expected_instances: Iterable[str],
    judge_instance: str | None = None,
) -> TeamAggregate:
    """Resolve validated decisions without voting over arbitrary free text."""
    expected = tuple(dict.fromkeys(expected_instances))
    latest = _latest_by_instance(results)
    candidates = [
        result
        for instance_id in expected
        if (result := latest.get(instance_id)) is not None
        and result.decision is not None
    ]
    participants = tuple(item.instance_id for item in candidates)
    failed = tuple(
        instance_id
        for instance_id in expected
        if instance_id not in participants
    )
    participation = len(candidates) / len(expected) if expected else 0.0
    if participation < quorum:
        return TeamAggregate(
            status="no_quorum",
            policy=policy,
            decision=_safe_rejection("Configured Agent quorum was not reached."),
            participants=participants,
            failed_instances=failed,
        )

    if policy == "judge":
        judge = latest.get(judge_instance or "")
        if judge is None or judge.decision is None:
            decision = _safe_rejection("The configured judge produced no decision.")
        else:
            decision = judge.decision
    elif policy == "most_conservative":
        decision = _most_conservative(candidates)
    elif policy in {"majority_vote", "weighted_vote"}:
        decision = _vote(candidates, weighted=policy == "weighted_vote")
    else:
        kinds = {
            item.decision.decision
            for item in candidates
            if item.decision is not None and item.decision.decision != "abstain"
        }
        if len(kinds) != 1:
            decision = _safe_rejection(
                "Reject-on-conflict policy found disagreement or no affirmative decision."
            )
        else:
            only_kind = next(iter(kinds))
            matching = [
                item
                for item in candidates
                if item.decision is not None
                and item.decision.decision == only_kind
            ]
            decision = _most_conservative(matching)
    return TeamAggregate(
        status="rejected" if decision.decision == "reject" else "resolved",
        policy=policy,
        decision=decision,
        participants=participants,
        failed_instances=failed,
    )
