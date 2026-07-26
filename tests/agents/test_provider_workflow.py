from __future__ import annotations

from pathlib import Path

import yaml
from click import unstyle
from typer.testing import CliRunner

from crossmarket_agentgym.agents.config import load_provider_check_config
from crossmarket_agentgym.agents.workflow import execute_provider_check
from crossmarket_agentgym.cli.app import app


def _plain_cli_output(result: object) -> str:
    stdout = getattr(result, "stdout", "")
    stderr = getattr(result, "stderr", "")
    return " ".join(unstyle(stdout + stderr).split())


def test_offline_provider_workflow_and_cli(tmp_path: Path) -> None:
    base = load_provider_check_config(Path("configs/agents/provider_offline.yaml"))
    config = base.model_copy(
        update={
            "run_id": "phase5-workflow-test",
            "output_dir": tmp_path,
        }
    )
    summary = execute_provider_check(config)
    assert summary.used_fallback is False
    assert summary.tool_calls == 1
    assert summary.replay_verified is True
    assert summary.network_used is False
    assert summary.output.safe_to_continue is True

    cli_config = config.model_copy(
        update={"run_id": "phase5-cli-test"}
    )
    config_path = tmp_path / "provider-check.yaml"
    config_path.write_text(
        yaml.safe_dump(cli_config.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        ["agent", "provider-check", "--config", str(config_path)],
    )
    assert result.exit_code == 0
    assert '"replay_verified": true' in result.stdout
    assert '"network_used": false' in result.stdout


def test_provider_check_requires_explicit_config() -> None:
    result = CliRunner().invoke(app, ["agent", "provider-check"], color=True)
    assert result.exit_code == 2
    assert "--config is required" in _plain_cli_output(result)


def test_online_deepseek_configuration_contains_environment_names_only() -> None:
    config = load_provider_check_config(
        Path("configs/agents/provider_online_deepseek.yaml")
    )
    assert config.provider.provider == "openai_compatible"
    assert config.provider.model == "deepseek-v4-pro"
    assert config.provider.api_key_env == "DEEPSEEK_API_KEY"
    assert config.mock_script == ()
