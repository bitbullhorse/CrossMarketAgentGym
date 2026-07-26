from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from crossmarket_agentgym.agents.config import load_agent_runtime_config
from crossmarket_agentgym.agents.runtime_workflow import execute_agent_runtime
from crossmarket_agentgym.cli.app import app


def test_offline_single_runtime_workflow_and_cli(tmp_path: Path) -> None:
    base = load_agent_runtime_config(
        Path("configs/agents/runtime_single_offline.yaml")
    )
    config = base.model_copy(
        update={
            "run_id": "phase6-single-workflow-test",
            "output_dir": tmp_path,
        }
    )
    summary = execute_agent_runtime(config)
    assert summary.configured_instances == 1
    assert summary.succeeded == 1
    assert summary.network_used is False
    assert summary.aggregate.decision.decision == "approve"

    cli_config = config.model_copy(update={"run_id": "phase6-single-cli-test"})
    config_path = tmp_path / "runtime-single.yaml"
    config_path.write_text(
        yaml.safe_dump(cli_config.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        ["agent", "run", "--config", str(config_path)],
    )
    assert result.exit_code == 0
    assert '"configured_instances": 1' in result.stdout
    assert '"network_used": false' in result.stdout


def test_offline_one_plus_three_plus_two_workflow(tmp_path: Path) -> None:
    base = load_agent_runtime_config(
        Path("configs/agents/runtime_team_offline.yaml")
    )
    config = base.model_copy(
        update={
            "run_id": "phase6-team-workflow-test",
            "output_dir": tmp_path,
        }
    )
    summary = execute_agent_runtime(config)
    assert summary.configured_instances == 6
    assert summary.succeeded == 5
    assert summary.fallback == 1
    assert summary.failed == 0
    assert summary.aggregate.status == "rejected"
    assert summary.aggregate.decision.constraints.cash_floor == 1.0
    assert (tmp_path / config.run_id / "config.sha256").exists()
    assert (
        tmp_path / config.run_id / "agent" / "team.resolved.json"
    ).exists()


def test_runtime_cli_requires_explicit_config() -> None:
    result = CliRunner().invoke(app, ["agent", "run"])
    assert result.exit_code == 2
    assert "--config is required" in (result.stdout + result.stderr)


def test_online_runtime_config_is_credential_free_and_three_layered() -> None:
    config = load_agent_runtime_config(
        Path("configs/agents/runtime_deepseek_team.yaml")
    )
    assert {agent.type for agent in config.team.agents} == {
        "research_coordinator",
        "risk_manager",
        "market_regime",
    }
    assert all(agent.model == "deepseek-v4-pro" for agent in config.team.agents)
    assert all(
        agent.api_key_env == "DEEPSEEK_API_KEY"
        for agent in config.team.agents
    )
