from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from crossmarket_agentgym.agents import (
    AgentRuntimeConfig,
    AgentSpec,
    TeamSpec,
    expand_agent_specs,
)
from crossmarket_agentgym.agents.providers import MockTurn


def _mock_spec(name: str, *, count: int = 1, enabled: bool = True) -> AgentSpec:
    return AgentSpec(
        type="research_coordinator",
        name=name,
        count=count,
        enabled=enabled,
        provider="mock",
        mock_scripts=(
            (
                MockTurn(
                    content={
                        "decision": "approve",
                        "summary": "ok",
                    }
                ),
            ),
        ),
    )


def test_dynamic_count_has_independent_ids_and_stable_seeds() -> None:
    config = AgentRuntimeConfig(
        run_id="count-test",
        workspace_root=Path.cwd(),
        objective="Review",
        team=TeamSpec(
            topology="committee_vote",
            agents=(_mock_spec("risk_reviewer", count=3),),
        ),
    )
    first = expand_agent_specs(config)
    second = expand_agent_specs(config)
    assert [item.instance_id for item in first] == [
        "risk_reviewer_0",
        "risk_reviewer_1",
        "risk_reviewer_2",
    ]
    assert len({item.seed for item in first}) == 3
    assert [item.seed for item in first] == [item.seed for item in second]


def test_disabled_agent_is_not_expanded() -> None:
    config = AgentRuntimeConfig(
        run_id="disabled-test",
        objective="Review",
        team=TeamSpec(
            topology="single",
            agents=(
                _mock_spec("active"),
                _mock_spec("disabled", enabled=False),
            ),
        ),
    )
    assert [item.instance_id for item in expand_agent_specs(config)] == ["active"]


@pytest.mark.parametrize(
    ("team", "message"),
    [
        (
            {
                "topology": "single",
                "agents": [_mock_spec("many", count=2)],
            },
            "exactly one",
        ),
        (
            {
                "topology": "supervisor_worker",
                "agents": [_mock_spec("worker")],
                "supervisor": "missing",
            },
            "supervisor",
        ),
        (
            {
                "topology": "debate_then_judge",
                "agents": [_mock_spec("judge")],
                "judge": "judge",
                "max_rounds": 1,
            },
            "max_rounds",
        ),
    ],
)
def test_invalid_topologies_fail_during_schema_validation(
    team: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        TeamSpec.model_validate(team)


def test_mock_count_accepts_per_instance_scripts() -> None:
    script = (MockTurn(content={"decision": "approve", "summary": "ok"}),)
    spec = AgentSpec(
        type="risk_manager",
        name="risk",
        count=2,
        provider="mock",
        mock_scripts=(script, script),
    )
    assert spec.mock_script(0) == script
    assert spec.mock_script(1) == script


def test_every_agent_enforces_required_model() -> None:
    with pytest.raises(ValidationError, match="deepseek-v4-pro"):
        AgentSpec(
            type="risk_manager",
            name="risk",
            provider="mock",
            model="another-model",
            mock_scripts=((MockTurn(content={}),),),
        )
