from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from crossmarket_agentgym.agents.directives import RiskDirective
from crossmarket_agentgym.agents.layer_config import (
    Phase7RunConfig,
    load_phase7_run_config,
)
from crossmarket_agentgym.agents.layer_stack import (
    execute_phase7_stack,
    replay_phase7_bundle,
)
from crossmarket_agentgym.audit.directives import load_directive_journal
from crossmarket_agentgym.cli.app import app

_PRESETS = {
    "no_llm": (False, False, False),
    "research_only": (True, False, False),
    "risk_only": (False, True, False),
    "hierarchical_only": (False, False, True),
    "research_plus_risk": (True, True, False),
    "full_stack": (True, True, True),
}


def _preset_config(
    tmp_path: Path,
    preset: str,
    *,
    as_of_index: int = 0,
    previous_risk: RiskDirective | None = None,
) -> Phase7RunConfig:
    base = load_phase7_run_config(
        Path("configs/agents/phase7_full_stack_offline.yaml")
    )
    research_enabled, risk_enabled, hierarchical_enabled = _PRESETS[preset]
    research = base.layers.research.model_copy(
        update={
            "enabled": research_enabled,
            "team": base.layers.research.team if research_enabled else None,
        }
    )
    risk = base.layers.risk.model_copy(
        update={
            "enabled": risk_enabled,
            "team": base.layers.risk.team if risk_enabled else None,
            "previous_directive": previous_risk,
        }
    )
    hierarchical = base.layers.hierarchical.model_copy(
        update={
            "enabled": hierarchical_enabled,
            "team": (
                base.layers.hierarchical.team
                if hierarchical_enabled
                else None
            ),
        }
    )
    raw = base.model_dump(mode="json")
    raw.update(
        {
            "run_id": f"phase7-preset-{preset}-{as_of_index}",
            "output_dir": str(tmp_path),
            "preset": preset,
            "as_of_index": as_of_index,
            "layers": {
                "research": research.model_dump(mode="json"),
                "risk": risk.model_dump(mode="json"),
                "hierarchical": hierarchical.model_dump(mode="json"),
            },
        }
    )
    return Phase7RunConfig.model_validate(raw)


@pytest.mark.parametrize("preset", tuple(_PRESETS))
def test_all_required_presets_run_offline(
    tmp_path: Path,
    preset: str,
) -> None:
    config = _preset_config(tmp_path, preset)
    summary = execute_phase7_stack(config)
    assert summary.preset == preset
    assert summary.provider_runtimes_started == sum(_PRESETS[preset])
    assert summary.network_used is False
    assert summary.directive_replay_verified is True
    assert abs(sum(summary.projection.projected_weights) - 1.0) < 1e-9
    assert (
        summary.fusion.constraints.max_asset_weight
        <= config.administrator_environment.max_asset_weight
    )
    assert (
        summary.fusion.constraints.cash_floor
        >= config.administrator_environment.cash_floor
    )
    assert (
        summary.fusion.constraints.max_turnover
        <= config.administrator_environment.max_turnover
    )


def test_no_llm_never_constructs_an_agent_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_phase7_run_config(
        Path("configs/agents/phase7_no_llm.yaml")
    ).model_copy(
        update={
            "run_id": "phase7-no-provider-construction",
            "output_dir": tmp_path,
        }
    )

    class ForbiddenRuntime:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs
            raise AssertionError("no_llm constructed AgentRuntime")

    monkeypatch.setattr(
        "crossmarket_agentgym.agents.layer_stack.AgentRuntime",
        ForbiddenRuntime,
    )
    summary = execute_phase7_stack(config)
    assert summary.provider_runtimes_started == 0
    assert summary.network_used is False


def test_not_due_layer_reuses_previous_directive_without_provider(
    tmp_path: Path,
) -> None:
    base = load_phase7_run_config(
        Path("configs/agents/phase7_full_stack_offline.yaml")
    )
    previous = RiskDirective(
        risk_budget=0.5,
        max_asset_weight=0.1,
        max_market_weights={"CN": 0.2, "HK": 0.2, "JP": 0.2, "US": 0.2},
        cash_floor=0.5,
        max_turnover=0.1,
        allow_new_positions=False,
        rebalance_frequency="weekly",
        rationale="previous audited weekly directive",
        confidence=0.9,
    )
    config = _preset_config(
        tmp_path,
        "risk_only",
        as_of_index=1,
        previous_risk=previous,
    )
    summary = execute_phase7_stack(config)
    assert summary.risk.due is False
    assert summary.risk.source == "previous"
    assert summary.risk.directive == previous
    assert summary.provider_runtimes_started == 0
    assert base.layers.risk.cadence == "weekly"


def test_risk_provider_failure_uses_static_no_position_fallback(
    tmp_path: Path,
) -> None:
    config = _preset_config(tmp_path, "risk_only")
    raw = config.model_dump(mode="json")
    raw["run_id"] = "phase7-risk-provider-fallback"
    risk_agent = raw["layers"]["risk"]["team"]["agents"][0]
    risk_agent["mock_scripts"] = [
        [
            {
                "error_code": "risk_provider_unavailable",
                "error_message": "offline failure",
            }
        ]
    ]
    failed_config = Phase7RunConfig.model_validate(raw)
    summary = execute_phase7_stack(failed_config)
    assert summary.risk.source == "fallback"
    assert summary.risk.merge.effective.allow_new_positions is False
    assert summary.risk.merge.effective.cash_floor == 1.0
    assert summary.projection.projected_weights == (1.0, 0.0, 0.0, 0.0, 0.0)


def test_aggressive_risk_output_is_clipped_by_hard_policy(
    tmp_path: Path,
) -> None:
    config = _preset_config(tmp_path, "risk_only")
    raw = config.model_dump(mode="json")
    raw["run_id"] = "phase7-risk-hard-policy-clipping"
    team = raw["layers"]["risk"]["team"]
    team["agents"][0]["count"] = 1
    team["agents"][0]["mock_scripts"] = [
        team["agents"][0]["mock_scripts"][0]
    ]
    aggressive = Phase7RunConfig.model_validate(raw)
    summary = execute_phase7_stack(aggressive)
    hard = aggressive.administrator_environment
    effective = summary.risk.merge.effective
    assert effective.max_asset_weight == hard.max_asset_weight
    assert effective.cash_floor == hard.cash_floor
    assert effective.max_turnover == hard.max_turnover
    assert "max_asset_weight" in summary.risk.merge.clipped_fields
    assert "cash_floor" in summary.risk.merge.clipped_fields
    assert "max_turnover" in summary.risk.merge.clipped_fields


def test_directive_journal_and_replay_are_hash_verified(tmp_path: Path) -> None:
    config = _preset_config(tmp_path, "full_stack")
    summary = execute_phase7_stack(config)
    run_dir = tmp_path / config.run_id
    journal_path = run_dir / "agent" / "directives.jsonl"
    records = load_directive_journal(journal_path)
    assert [record.kind for record in records] == [
        "research",
        "risk_proposed",
        "risk_effective",
        "hierarchical",
        "fusion",
        "projection",
    ]
    replayed = replay_phase7_bundle(
        run_dir / "agent" / "directive_replay.json"
    )
    assert replayed == summary.projection

    lines = journal_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["payload"]["confidence"] = 0.123
    lines[0] = json.dumps(first)
    journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_directive_journal(journal_path)


def test_phase7_cli_dispatches_from_agent_run(tmp_path: Path) -> None:
    base = load_phase7_run_config(Path("configs/agents/phase7_no_llm.yaml"))
    config = base.model_copy(
        update={"run_id": "phase7-cli-test", "output_dir": tmp_path}
    )
    config_path = tmp_path / "phase7-cli.yaml"
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        ["agent", "run", "--config", str(config_path)],
    )
    assert result.exit_code == 0
    assert '"preset": "no_llm"' in result.stdout
    assert '"provider_runtimes_started": 0' in result.stdout
