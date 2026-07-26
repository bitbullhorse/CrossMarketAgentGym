from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from crossmarket_agentgym.agents import (
    AgentDecision,
    AgentRuntime,
    AgentRuntimeConfig,
    AgentSpec,
    DecisionConstraints,
    TeamSpec,
)
from crossmarket_agentgym.agents.models import (
    AgentContext,
    AgentInstance,
    RoleInvocation,
)
from crossmarket_agentgym.agents.providers import MockTurn
from crossmarket_agentgym.agents.roles import AgentRegistry, RoleServices


class _ScriptedRole:
    def __init__(self, instance: AgentInstance) -> None:
        self.instance = instance
        self.calls = 0

    def run(self, context: AgentContext) -> RoleInvocation:
        self.calls += 1
        metadata = self.instance.spec.metadata
        if metadata.get("fail_first") and self.calls == 1:
            raise RuntimeError("transient plugin failure")
        if self.instance.index in metadata.get("fail_indices", []):
            raise RuntimeError("deliberate plugin failure password=not-persisted")
        delay = float(metadata.get("delay", 0.0))
        if delay:
            time.sleep(delay)
        kind = str(metadata.get("decision", "approve"))
        constraints = DecisionConstraints.model_validate(
            metadata.get("constraints", {})
        )
        return RoleInvocation(
            decision=AgentDecision(
                decision=kind,  # type: ignore[arg-type]
                summary=f"{self.instance.instance_id} round {context.round_index}",
                confidence=0.8,
                risk_score=float(metadata.get("risk_score", 0.2)),
                constraints=constraints,
                payload={"upstream_count": len(context.upstream)},
            )
        )

    def close(self) -> None:
        pass


def _factory(
    instance: AgentInstance,
    services: RoleServices,
) -> _ScriptedRole:
    del services
    return _ScriptedRole(instance)


def _registry() -> AgentRegistry:
    registry = AgentRegistry(include_builtins=False)
    registry.register("custom_role", _factory)
    return registry


def _spec(
    name: str,
    *,
    count: int = 1,
    decision: str = "approve",
    fail_indices: list[int] | None = None,
    timeout: float = 1.0,
    delay: float = 0.0,
    max_retries: int = 0,
    fail_first: bool = False,
) -> AgentSpec:
    return AgentSpec(
        type="custom_role",
        name=name,
        count=count,
        provider="mock",
        mock_scripts=((MockTurn(content={"unused": True}),),),
        timeout_seconds=timeout,
        max_retries=max_retries,
        metadata={
            "decision": decision,
            "fail_indices": fail_indices or [],
            "delay": delay,
            "fail_first": fail_first,
        },
    )


def _config(
    tmp_path: Path,
    topology: str,
    agents: tuple[AgentSpec, ...],
    **team_updates: Any,
) -> AgentRuntimeConfig:
    team = TeamSpec(
        topology=topology,  # type: ignore[arg-type]
        agents=agents,
        **team_updates,
    )
    return AgentRuntimeConfig(
        run_id=f"runtime-{topology}-{len(list(tmp_path.iterdir()))}",
        workspace_root=Path.cwd(),
        output_dir=tmp_path,
        objective="Return a structured review.",
        load_entry_points=False,
        team=team,
    )


@pytest.mark.parametrize(
    ("topology", "agents", "updates", "expected_rounds"),
    [
        ("single", (_spec("solo"),), {}, 1),
        ("pipeline", (_spec("first"), _spec("second")), {}, 1),
        (
            "supervisor_worker",
            (_spec("supervisor"), _spec("worker")),
            {"supervisor": "supervisor", "max_rounds": 2},
            2,
        ),
        (
            "committee_vote",
            (_spec("member", count=2),),
            {},
            1,
        ),
        (
            "debate_then_judge",
            (_spec("debater"), _spec("judge")),
            {"judge": "judge", "max_rounds": 2},
            2,
        ),
        (
            "map_reduce",
            (_spec("mapper"), _spec("reducer")),
            {"supervisor": "reducer", "max_rounds": 2},
            2,
        ),
    ],
)
def test_all_six_topologies(
    tmp_path: Path,
    topology: str,
    agents: tuple[AgentSpec, ...],
    updates: dict[str, object],
    expected_rounds: int,
) -> None:
    config = _config(tmp_path, topology, agents, **updates)
    runtime = AgentRuntime(
        config,
        run_dir=tmp_path / config.run_id,
        registry=_registry(),
    )
    try:
        result = runtime.run()
    finally:
        runtime.close()
    assert result.topology == topology
    assert result.rounds == expected_rounds
    assert result.aggregate.status == "resolved"
    assert result.failed == 0


@pytest.mark.parametrize("parallel", [False, True])
def test_parallel_and_serial_committee_have_same_resolution(
    tmp_path: Path,
    parallel: bool,
) -> None:
    config = _config(
        tmp_path,
        "committee_vote",
        (_spec("member", count=3),),
        parallel=parallel,
        conflict_policy="majority_vote",
    )
    runtime = AgentRuntime(
        config,
        run_dir=tmp_path / config.run_id,
        registry=_registry(),
    )
    try:
        result = runtime.run()
    finally:
        runtime.close()
    assert result.parallel is parallel
    assert result.aggregate.decision.decision == "approve"
    assert [item.instance_id for item in result.results] == [
        "member_0",
        "member_1",
        "member_2",
    ]


def test_one_plus_three_plus_two_team_continues_after_partial_failure(
    tmp_path: Path,
) -> None:
    config = _config(
        tmp_path,
        "committee_vote",
        (
            _spec("coordinator"),
            _spec("risk", count=3, decision="revise", fail_indices=[1]),
            _spec("auditor", count=2),
        ),
        quorum=0.5,
        parallel=True,
        conflict_policy="most_conservative",
    )
    runtime = AgentRuntime(
        config,
        run_dir=tmp_path / config.run_id,
        registry=_registry(),
    )
    try:
        result = runtime.run()
    finally:
        runtime.close()
    assert result.configured_instances == 6
    assert result.succeeded == 5
    assert result.failed == 1
    assert result.aggregate.status == "resolved"
    assert result.aggregate.decision.decision == "revise"
    events = (
        tmp_path
        / config.run_id
        / "agent"
        / "runtime_events.jsonl"
    ).read_text(encoding="utf-8")
    assert "not-persisted" not in events


def test_agent_timeout_isolated_and_fails_closed(tmp_path: Path) -> None:
    config = _config(
        tmp_path,
        "committee_vote",
        (
            _spec("fast"),
            _spec("slow", timeout=0.01, delay=0.05),
        ),
        quorum=1.0,
    )
    runtime = AgentRuntime(
        config,
        run_dir=tmp_path / config.run_id,
        registry=_registry(),
    )
    try:
        result = runtime.run()
    finally:
        runtime.close()
    assert result.timed_out == 1
    assert result.aggregate.status == "no_quorum"


def test_per_instance_retry_recovers_transient_plugin_failure(
    tmp_path: Path,
) -> None:
    config = _config(
        tmp_path,
        "single",
        (_spec("retrying", max_retries=1, fail_first=True),),
    )
    runtime = AgentRuntime(
        config,
        run_dir=tmp_path / config.run_id,
        registry=_registry(),
    )
    try:
        result = runtime.run()
    finally:
        runtime.close()
    assert result.succeeded == 1
    assert result.results[0].attempts == 2


def test_builtin_provider_role_uses_shared_runtime_and_static_schema(
    tmp_path: Path,
) -> None:
    spec = AgentSpec(
        type="research_coordinator",
        name="research",
        provider="mock",
        mock_scripts=(
            (
                MockTurn(
                    content={
                        "decision": "approve",
                        "summary": "offline research complete",
                        "confidence": 0.9,
                        "risk_score": 0.1,
                    }
                ),
            ),
        ),
    )
    config = AgentRuntimeConfig(
        run_id="builtin-single",
        workspace_root=Path.cwd(),
        objective="Inspect the experiment.",
        load_entry_points=False,
        team=TeamSpec(topology="single", agents=(spec,)),
    )
    runtime = AgentRuntime(config, run_dir=tmp_path / config.run_id)
    try:
        result = runtime.run()
    finally:
        runtime.close()
    assert result.network_used is False
    assert result.results[0].decision is not None
    assert result.results[0].decision.summary == "offline research complete"
    assert (
        tmp_path
        / config.run_id
        / "agent_instances"
        / "research"
        / "agent"
        / "replay.jsonl"
    ).exists()
