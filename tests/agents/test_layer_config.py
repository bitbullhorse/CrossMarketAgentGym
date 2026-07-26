from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from crossmarket_agentgym.agents.layer_config import (
    Phase7RunConfig,
    load_phase7_run_config,
)


def test_offline_and_online_phase7_configs_are_strict_and_credential_free() -> None:
    offline = load_phase7_run_config(
        Path("configs/agents/phase7_full_stack_offline.yaml")
    )
    online = load_phase7_run_config(Path("configs/agents/full_stack.yaml"))
    assert offline.preset == online.preset == "full_stack"
    assert all(
        agent.model == "deepseek-v4-pro"
        for layer in (
            online.layers.research,
            online.layers.risk,
            online.layers.hierarchical,
        )
        for agent in (layer.team.agents if layer.team is not None else ())
    )
    assert all(
        agent.api_key_env == "DEEPSEEK_API_KEY"
        for layer in (
            online.layers.research,
            online.layers.risk,
            online.layers.hierarchical,
        )
        for agent in (layer.team.agents if layer.team is not None else ())
    )


def test_preset_must_match_enabled_layers() -> None:
    raw = load_phase7_run_config(
        Path("configs/agents/phase7_no_llm.yaml")
    ).model_dump(mode="json")
    raw["preset"] = "risk_only"
    with pytest.raises(ValidationError, match="do not match preset"):
        Phase7RunConfig.model_validate(raw)


def test_disabled_layer_cannot_hide_a_configured_team() -> None:
    raw = load_phase7_run_config(
        Path("configs/agents/phase7_full_stack_offline.yaml")
    ).model_dump(mode="json")
    raw["preset"] = "custom"
    raw["layers"]["research"]["enabled"] = False
    with pytest.raises(ValidationError, match="disabled LLM layer"):
        Phase7RunConfig.model_validate(raw)


def test_plan_only_cannot_expose_tools() -> None:
    raw = load_phase7_run_config(
        Path("configs/agents/phase7_full_stack_offline.yaml")
    ).model_dump(mode="json")
    raw["layers"]["research"]["mode"] = "plan_only"
    with pytest.raises(ValidationError, match="plan_only"):
        Phase7RunConfig.model_validate(raw)


def test_multi_risk_committee_requires_conservative_policy() -> None:
    raw = load_phase7_run_config(
        Path("configs/agents/phase7_full_stack_offline.yaml")
    ).model_dump(mode="json")
    raw["layers"]["risk"]["team"]["conflict_policy"] = "majority_vote"
    with pytest.raises(ValidationError, match="most_conservative"):
        Phase7RunConfig.model_validate(raw)


def test_projection_vector_geometry_is_validated() -> None:
    raw = load_phase7_run_config(
        Path("configs/agents/phase7_no_llm.yaml")
    ).model_dump(mode="json")
    raw["raw_action"] = [1.0]
    with pytest.raises(ValidationError, match="raw_action length"):
        Phase7RunConfig.model_validate(raw)


def test_execute_mode_requires_budget_gate_for_expensive_tools() -> None:
    raw = load_phase7_run_config(
        Path("configs/agents/phase7_full_stack_offline.yaml")
    ).model_dump(mode="json")
    research = raw["layers"]["research"]
    research["mode"] = "execute"
    agent = research["team"]["agents"][0]
    agent["tools"] = ["train_rl"]
    agent["allowed_permissions"] = ["expensive"]
    agent["max_expensive_tool_calls"] = 1
    with pytest.raises(ValidationError, match="budget estimation"):
        Phase7RunConfig.model_validate(raw)
