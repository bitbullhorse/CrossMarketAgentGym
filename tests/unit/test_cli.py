"""CLI command-tree smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click import unstyle
from typer.testing import CliRunner

from crossmarket_agentgym.audit.run_manifest import verify_run_manifest
from crossmarket_agentgym.cli.app import app
from crossmarket_agentgym.rl import CallbackConfig, TrainerConfig, load_train_run_config

runner = CliRunner()


def _plain_cli_output(result: object) -> str:
    stdout = getattr(result, "stdout", "")
    stderr = getattr(result, "stderr", "")
    return " ".join(unstyle(stdout + stderr).split())


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
    assert result.stdout.strip() == "1.0.0rc2"


def test_reproduce_requires_run_id() -> None:
    result = runner.invoke(app, ["reproduce"], color=True)

    assert result.exit_code == 2
    assert "--run-id is required" in _plain_cli_output(result)


def test_phase3_commands_require_explicit_artifacts() -> None:
    """Training and locked evaluation never guess their input targets."""
    train_result = runner.invoke(app, ["train"], color=True)
    evaluate_result = runner.invoke(app, ["evaluate"], color=True)
    tune_result = runner.invoke(app, ["tune"], color=True)

    assert train_result.exit_code == 2
    assert "--config is required" in _plain_cli_output(train_result)
    assert evaluate_result.exit_code == 2
    assert "--run-id is required" in _plain_cli_output(evaluate_result)
    assert tune_result.exit_code == 2
    assert "--config is required" in _plain_cli_output(tune_result)


def test_phase8_commands_require_explicit_configuration() -> None:
    report_result = runner.invoke(app, ["report", "softwarex"], color=True)
    service_result = runner.invoke(app, ["service", "run"], color=True)

    assert report_result.exit_code == 2
    assert "--config is required" in _plain_cli_output(report_result)
    assert service_result.exit_code == 2
    assert "--config is required" in _plain_cli_output(service_result)


def test_report_run_id_prints_one_whitelisted_record(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "report-example"
    validation = run_dir / "validation"
    validation.mkdir(parents=True)
    (run_dir / "run_summary.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "run_id": "report-example",
                "algorithm": "PPO",
                "requested_timesteps": 8,
                "trained_timesteps": 8,
            }
        ),
        encoding="utf-8",
    )
    (validation / "metrics.json").write_text(
        '{"metrics": {"sharpe": 0.5}}\n',
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "report",
            "--run-id",
            "report-example",
            "--workspace-root",
            str(tmp_path),
            "--runs-root",
            "runs",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["run_id"] == "report-example"
    assert payload["kind"] == "training"
    assert payload["metrics"]["validation"]["sharpe"] == 0.5


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
    manifest = verify_run_manifest(tmp_path / "cli_phase3")
    assert {item.relative_path for item in manifest.artifacts} >= {
        "validation/metrics.json",
        "test/metrics.json",
    }


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
    result = runner.invoke(app, ["data", "validate"], color=True)

    assert result.exit_code == 2
    assert "--config is required" in _plain_cli_output(result)


def test_env_check_runs_phase2_smoke() -> None:
    """The Phase 2 command runs compatibility and accounting checks."""
    result = runner.invoke(
        app,
        ["env", "check", "--config", "configs/env/cross_market.yaml"],
    )

    assert result.exit_code == 0
    assert '"is_valid": true' in result.stdout
    assert '"smoke_steps": 1000' in result.stdout
    assert '"market_window_layout": "flat"' in result.stdout
    assert '"warnings": []' in result.stdout


def test_env_check_explains_tensor_image_heuristic(tmp_path: Path) -> None:
    """Tensor financial data produces an accepted structured SB3 explanation."""
    raw = yaml.safe_load(
        Path("configs/env/sample_cross_market.yaml").read_text(encoding="utf-8")
    )
    raw["smoke_steps"] = 1
    raw["observation"] = {"market_window_layout": "tensor"}
    config_path = tmp_path / "tensor_env.yaml"
    config_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    result = runner.invoke(
        app,
        ["env", "check", "--config", str(config_path)],
    )

    assert result.exit_code == 0
    assert '"warning_code": "SB3_BOX_IMAGE_HEURISTIC"' in result.stdout
    assert '"accepted": true' in result.stdout
    assert '"required_policy": "custom_features_extractor"' in result.stdout
