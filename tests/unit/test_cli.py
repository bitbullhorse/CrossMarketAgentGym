"""CLI command-tree smoke tests."""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from crossmarket_agentgym.cli.app import app
from crossmarket_agentgym.rl import CallbackConfig, TrainerConfig, load_train_run_config

runner = CliRunner()


def test_help_lists_stable_commands() -> None:
    """The Phase 0 CLI advertises every command reserved by the report."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in (
        "data",
        "env",
        "train",
        "evaluate",
        "tune",
        "agent",
        "report",
        "service",
        "release",
        "quickstart",
        "reproduce",
    ):
        assert command in result.stdout


def test_version_option() -> None:
    """The eager version option does not require a subcommand."""
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "0.1.0"


def test_reproduce_requires_run_id() -> None:
    result = runner.invoke(app, ["reproduce"])

    assert result.exit_code == 2
    assert "--run-id is required" in (result.stdout + result.stderr)


def test_phase3_commands_require_explicit_artifacts() -> None:
    """Training and locked evaluation never guess their input targets."""
    train_result = runner.invoke(app, ["train"])
    evaluate_result = runner.invoke(app, ["evaluate"])
    tune_result = runner.invoke(app, ["tune"])

    assert train_result.exit_code == 2
    assert "--config is required" in (train_result.stdout + train_result.stderr)
    assert evaluate_result.exit_code == 2
    assert "--run-id is required" in (
        evaluate_result.stdout + evaluate_result.stderr
    )
    assert tune_result.exit_code == 2
    assert "--config is required" in (tune_result.stdout + tune_result.stderr)


def test_phase8_commands_require_explicit_configuration() -> None:
    report_result = runner.invoke(app, ["report", "softwarex"])
    service_result = runner.invoke(app, ["service", "run"])

    assert report_result.exit_code == 2
    assert "--config is required" in (report_result.stdout + report_result.stderr)
    assert service_result.exit_code == 2
    assert "--config is required" in (service_result.stdout + service_result.stderr)


def test_train_and_locked_evaluate_cli(tmp_path) -> None:
    """Phase 3 CLI writes validation first and test only on evaluate."""
    base = load_train_run_config(Path("configs/train/ppo.yaml"))
    config = base.model_copy(
        update={
            "output_dir": tmp_path,
            "run_name": "cli_phase3",
            "trainer": TrainerConfig(
                algorithm="PPO",
                policy="mlp",
                total_timesteps=8,
                n_steps=8,
                batch_size=4,
                n_epochs=1,
                features_dim=16,
                net_arch=(16,),
            ),
            "callbacks": CallbackConfig(
                checkpoint_freq=0,
                validation_freq=0,
                early_stop_patience=0,
                resource_monitor_freq=0,
                audit_freq=0,
                metrics_freq=0,
            ),
        }
    )
    config_path = tmp_path / "train.yaml"
    config_path.write_text(
        yaml.safe_dump(config.model_dump(mode="json")),
        encoding="utf-8",
    )

    train_result = runner.invoke(app, ["train", "--config", str(config_path)])
    evaluate_result = runner.invoke(
        app,
        ["evaluate", "--run-id", str(tmp_path / "cli_phase3")],
    )

    assert train_result.exit_code == 0
    assert '"algorithm": "PPO"' in train_result.stdout
    assert evaluate_result.exit_code == 0
    assert '"partition": "test"' in evaluate_result.stdout


def test_data_validate_runs_phase1_sample() -> None:
    """The Phase 1 command validates data instead of returning a placeholder."""
    result = runner.invoke(
        app,
        ["data", "validate", "--config", "configs/data/sample.yaml"],
    )

    assert result.exit_code == 0
    assert '"is_valid": true' in result.stdout
    assert '"ohlcv_rows": 20' in result.stdout


def test_data_validate_requires_config() -> None:
    """Omitting a dataset reference fails before any filesystem work."""
    result = runner.invoke(app, ["data", "validate"])

    assert result.exit_code == 2
    assert "--config is required" in (result.stdout + result.stderr)


def test_env_check_runs_phase2_smoke() -> None:
    """The Phase 2 command runs compatibility and accounting checks."""
    result = runner.invoke(
        app,
        ["env", "check", "--config", "configs/env/cross_market.yaml"],
    )

    assert result.exit_code == 0
    assert '"is_valid": true' in result.stdout
    assert '"smoke_steps": 1000' in result.stdout
