from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from crossmarket_agentgym.agents.config import load_agent_runtime_config
from crossmarket_agentgym.agents.layer_config import load_phase7_run_config
from crossmarket_agentgym.agents.layer_stack import execute_phase7_stack
from crossmarket_agentgym.agents.runtime_workflow import execute_agent_runtime
from crossmarket_agentgym.audit.run_manifest import verify_run_manifest
from crossmarket_agentgym.cli.app import app
from crossmarket_agentgym.release import reproduce_run
from crossmarket_agentgym.release.reproduction import (
    _classify_reproduction,
    _compare_statistically,
    execute_training_replay,
    load_reproduction_tolerance_config,
    verify_run_artifacts,
)
from crossmarket_agentgym.release.reproduction_models import (
    ReproductionToleranceConfig,
)
from crossmarket_agentgym.rl.artifacts import TrainingMetadata
from crossmarket_agentgym.rl.config import load_train_run_config
from crossmarket_agentgym.rl.workflow import execute_training_run
from crossmarket_agentgym.tuning.config import load_tuning_run_config

PROJECT_ROOT = Path(__file__).parents[2]
runner = CliRunner()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _training_run(workspace: Path, run_id: str = "training-repro") -> Path:
    base = load_train_run_config(PROJECT_ROOT / "configs" / "train" / "ppo.yaml")
    config = base.model_copy(
        update={
            "dataset_root": Path("data/sample"),
            "output_dir": Path("runs"),
            "run_name": run_id,
        }
    )
    run_dir = workspace / "runs" / run_id
    _write_json(run_dir / "resolved_config.json", config.model_dump(mode="json"))
    manifest_source = PROJECT_ROOT / "data" / "sample" / "dataset_manifest.json"
    manifest_path = workspace / "data" / "sample" / "dataset_manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_bytes(manifest_source.read_bytes())
    dataset_id = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    checkpoint = run_dir / "checkpoints" / "final_model.zip"
    checkpoint.parent.mkdir(parents=True)
    with zipfile.ZipFile(checkpoint, "w") as archive:
        archive.writestr("metadata.json", "{}")
    metadata = TrainingMetadata(
        algorithm=config.trainer.algorithm,
        policy=config.trainer.policy,
        requested_timesteps=config.trainer.total_timesteps,
        trained_timesteps=config.trainer.total_timesteps,
        seed=config.trainer.seed,
        config_sha256=hashlib.sha256(
            config.trainer.model_dump_json().encode()
        ).hexdigest(),
        checkpoint="checkpoints/final_model.zip",
        dataset_id=dataset_id,
        data_partition="train",
        dependencies={"python": "fixture"},
    )
    _write_json(run_dir / "training_artifact.json", metadata.model_dump(mode="json"))
    _write_json(
        run_dir / "run_summary.json",
        {
            "run_id": run_id,
            "algorithm": config.trainer.algorithm,
            "requested_timesteps": config.trainer.total_timesteps,
            "trained_timesteps": config.trainer.total_timesteps,
        },
    )
    _write_json(
        run_dir / "validation" / "metrics.json",
        {"metrics": {"mean_return": 0.0, "max_drawdown": 0.0}},
    )
    return run_dir


def _tuning_run(workspace: Path, run_id: str = "tuning-repro") -> Path:
    base = load_tuning_run_config(
        PROJECT_ROOT / "configs" / "tune" / "ppo_pso_cpu.yaml"
    )
    run_dir = workspace / "runs" / "tuning" / run_id
    parameters = {"n_steps": 4, "batch_size": 2}
    _write_json(
        run_dir / "resolved_tuning_config.json",
        base.model_copy(update={"study_name": run_id}).model_dump(mode="json"),
    )
    _write_json(
        run_dir / "tuning_summary.json",
        {
            "study_name": run_id,
            "trial_count": 1,
            "completed_count": 1,
            "failed_count": 0,
            "best_trial_id": 0,
            "test_set_accessed": False,
        },
    )
    _write_json(
        run_dir / "study_report.json",
        {
            "study_name": run_id,
            "partition_policy": "train_and_validation_only",
            "test_metrics_present": False,
            "best_trial": {
                "parameters": parameters,
                "metrics": {"validation_median_sharpe": 0.1},
                "objectives": [0.1],
            },
        },
    )
    _write_json(
        run_dir / "locked_parameters.json",
        {
            "study_name": run_id,
            "parameters": parameters,
            "selected_on": "validation",
            "test_set_accessed": False,
        },
    )
    return run_dir


def _real_training_run(workspace: Path, run_id: str) -> Path:
    dataset_root = workspace / "data" / "sample"
    shutil.copytree(PROJECT_ROOT / "data" / "sample", dataset_root)
    base = load_train_run_config(
        PROJECT_ROOT / "configs" / "train" / "ppo_quickstart.yaml"
    )
    config = base.model_copy(
        update={
            "dataset_root": dataset_root,
            "output_dir": workspace / "runs",
            "run_name": run_id,
        }
    )
    execute_training_run(config)
    return workspace / "runs" / run_id


def _file_snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_training_reproduction_verifies_config_data_and_checkpoint(
    tmp_path: Path,
) -> None:
    run_dir = _training_run(tmp_path)
    result = reproduce_run(tmp_path, "runs", "training-repro")
    assert result.is_valid is True
    assert result.deterministic_replay is False
    assert result.network_used is False
    assert result.account_state_mutated is False

    config = json.loads(
        (run_dir / "resolved_config.json").read_text(encoding="utf-8")
    )
    config["trainer"]["gamma"] = 0.9
    _write_json(run_dir / "resolved_config.json", config)
    tampered = reproduce_run(tmp_path, "runs", "training-repro")
    assert tampered.is_valid is False
    assert any(
        item.name == "trainer_config_hash" and not item.passed
        for item in tampered.checks
    )


def test_tuning_reproduction_enforces_validation_only_selection(
    tmp_path: Path,
) -> None:
    run_dir = _tuning_run(tmp_path)
    result = reproduce_run(tmp_path, "runs", "tuning-repro")
    assert result.is_valid is True
    assert result.test_metrics_used_for_selection is False

    summary = json.loads(
        (run_dir / "tuning_summary.json").read_text(encoding="utf-8")
    )
    summary["test_set_accessed"] = True
    _write_json(run_dir / "tuning_summary.json", summary)
    unsafe = reproduce_run(tmp_path, "runs", "tuning-repro")
    assert unsafe.is_valid is False


def test_agent_and_phase7_reproduction_use_offline_replay(tmp_path: Path) -> None:
    agent_base = load_agent_runtime_config(
        PROJECT_ROOT / "configs" / "agents" / "runtime_single_offline.yaml"
    )
    agent_config = agent_base.model_copy(
        update={
            "workspace_root": tmp_path,
            "output_dir": Path("runs"),
            "run_id": "agent-repro",
        }
    )
    execute_agent_runtime(agent_config)
    agent = reproduce_run(tmp_path, "runs", "agent-repro")
    assert agent.is_valid is True
    assert agent.deterministic_replay is True

    phase7_base = load_phase7_run_config(
        PROJECT_ROOT / "configs" / "agents" / "phase7_no_llm.yaml"
    )
    phase7_config = phase7_base.model_copy(
        update={
            "workspace_root": tmp_path,
            "output_dir": Path("runs"),
            "run_id": "phase7-repro",
        }
    )
    execute_phase7_stack(phase7_config)
    phase7 = reproduce_run(tmp_path, "runs", "phase7-repro")
    assert phase7.is_valid is True
    assert phase7.deterministic_replay is True


def test_reproduce_cli_returns_strict_evidence(tmp_path: Path) -> None:
    _training_run(tmp_path, "cli-repro")
    result = runner.invoke(
        app,
        [
            "reproduce",
            "--run-id",
            "cli-repro",
            "--workspace-root",
            str(tmp_path),
            "--runs-root",
            "runs",
            "--verify-only",
        ],
    )
    assert result.exit_code == 0
    assert '"is_valid": true' in result.stdout
    assert '"verification_mode": "artifact_integrity"' in result.stdout
    assert '"artifact_integrity_verified": true' in result.stdout
    assert '"computational_replay_executed": false' in result.stdout
    assert '"reproduction_level": "artifact_verified"' in result.stdout
    assert '"network_used": false' in result.stdout


def test_artifact_verification_is_not_computational_replay(tmp_path: Path) -> None:
    _training_run(tmp_path, "artifact-only")

    result = verify_run_artifacts(tmp_path, "runs", "artifact-only")

    assert result.verification_mode == "artifact_integrity"
    assert result.artifact_integrity_verified is True
    assert result.computational_replay_executed is False
    assert result.reproduction_level == "artifact_verified"
    assert result.within_tolerance is None
    assert result.replay_run_id is None
    assert not (tmp_path / "runs" / "reproductions").exists()


def test_failed_computational_replay_is_retained_as_evidence(tmp_path: Path) -> None:
    source = _training_run(tmp_path, "incomplete-source")
    before = _file_snapshot(source)

    result = execute_training_replay(
        tmp_path,
        "runs",
        "incomplete-source",
        replay_run_id="failed-replay-evidence",
    )

    replay = (
        tmp_path
        / "runs"
        / "reproductions"
        / "incomplete-source"
        / "failed-replay-evidence"
    )
    assert result.is_valid is False
    assert result.reproduction_level == "failed"
    assert result.computational_replay_executed is False
    assert _file_snapshot(source) == before
    assert (replay / "reproduction_comparison.json").is_file()
    assert (replay / "reproduction_audit.jsonl").is_file()
    manifest = verify_run_manifest(replay)
    assert manifest.status == "failed"


@pytest.mark.integration
def test_execute_training_replay_retrains_and_compares_without_overwrite(
    tmp_path: Path,
) -> None:
    source = _real_training_run(tmp_path, "source-ppo")
    before = _file_snapshot(source)

    result = execute_training_replay(
        tmp_path,
        "runs",
        "source-ppo",
        replay_run_id="replay-source-ppo-test",
    )

    replay = (
        tmp_path
        / "runs"
        / "reproductions"
        / "source-ppo"
        / "replay-source-ppo-test"
    )
    assert result.is_valid is True
    assert result.verification_mode == "computational_replay"
    assert result.artifact_integrity_verified is True
    assert result.computational_replay_executed is True
    assert result.reproduction_level in {
        "bitwise_reproduced",
        "numerically_reproduced",
    }
    assert result.within_tolerance is True
    assert set(result.metric_comparison) == {
        "validation.mean_return",
        "validation.mean_reward",
        "validation.max_drawdown",
        "validation.mean_turnover",
        "validation.total_cost",
    }
    assert all(item.passed for item in result.metric_comparison.values())
    assert set(result.invariant_comparison) == {
        "trained_timesteps",
        "algorithm",
        "dataset_manifest_hash",
        "trainer_config_hash",
        "execution_protocol",
        "checkpoint_loadability",
    }
    assert all(item.passed for item in result.invariant_comparison.values())
    assert _file_snapshot(source) == before
    assert (replay / "source_run.json").is_file()
    assert (replay / "config.resolved.yaml").is_file()
    assert (replay / "reproduction_tolerance.resolved.yaml").is_file()
    assert (replay / "checkpoints" / "final_model.zip").is_file()
    assert (replay / "validation" / "metrics.json").is_file()
    assert (replay / "validation" / "trades.json").is_file()
    assert (replay / "validation" / "weights.json").is_file()
    assert (replay / "reproduction_audit.jsonl").is_file()
    assert (replay / "reproduction_comparison.json").is_file()
    assert not (replay / "test").exists()
    verify_run_manifest(replay)

    with pytest.raises(FileExistsError):
        execute_training_replay(
            tmp_path,
            "runs",
            "source-ppo",
            replay_run_id="replay-source-ppo-test",
        )


def test_reproduction_tolerance_file_is_strict(tmp_path: Path) -> None:
    reviewed = load_reproduction_tolerance_config(
        PROJECT_ROOT / "configs" / "reproduction" / "phase11_cpu.yaml"
    )
    assert reviewed.absolute_tolerance["mean_return"] == 1.0e-6
    assert reviewed.absolute_tolerance["total_cost"] == 1.0e-3
    assert reviewed.relative_tolerance.default == 1.0e-3
    assert reviewed.statistical.minimum_replays == 3

    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        """
schema_version: "1.0"
absolute_tolerance:
  mean_return: 1.0e-6
relative_tolerance:
  default: 1.0e-3
require_same:
  - trained_timesteps
statistical:
  minimum_replays: 3
  standard_error_multiplier: 2.0
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_reproduction_tolerance_config(invalid)


def test_reproduction_level_order_and_statistical_fallback(tmp_path: Path) -> None:
    assert _classify_reproduction(
        bitwise=True,
        numerically_passed=True,
        invariants_passed=True,
        statistically_passed=True,
        source_unchanged=True,
    ) == ("bitwise_reproduced", True)
    assert _classify_reproduction(
        bitwise=False,
        numerically_passed=True,
        invariants_passed=True,
        statistically_passed=True,
        source_unchanged=True,
    ) == ("numerically_reproduced", True)
    assert _classify_reproduction(
        bitwise=False,
        numerically_passed=False,
        invariants_passed=True,
        statistically_passed=True,
        source_unchanged=True,
    ) == ("statistically_reproduced", True)
    assert _classify_reproduction(
        bitwise=True,
        numerically_passed=True,
        invariants_passed=True,
        statistically_passed=True,
        source_unchanged=False,
    ) == ("failed", False)

    source = {name: 1.0 for name in (
        "mean_return",
        "mean_reward",
        "max_drawdown",
        "mean_turnover",
        "total_cost",
    )}
    current = dict(source)
    current["mean_return"] = 1.10
    for index, replay_value in enumerate((0.90, 1.00), start=1):
        comparison = {
            f"validation.{name}": {"replay": value}
            for name, value in source.items()
        }
        comparison["validation.mean_return"] = {"replay": replay_value}
        _write_json(
            tmp_path
            / f"prior-{index}"
            / "reproduction_comparison.json",
            {
                "source_run_id": tmp_path.name,
                "artifact_integrity_verified": True,
                "computational_replay_executed": True,
                "metric_comparison": comparison,
                "invariant_comparison": {
                    name: {"passed": True}
                    for name in (
                        "trained_timesteps",
                        "algorithm",
                        "dataset_manifest_hash",
                        "trainer_config_hash",
                        "execution_protocol",
                        "checkpoint_loadability",
                    )
                },
            },
        )

    comparison, passed = _compare_statistically(
        tmp_path,
        source,
        current,
        ReproductionToleranceConfig(),
        max_json_bytes=1_000_000,
    )

    assert passed is True
    assert comparison["validation.mean_return"].replay_count == 3
    assert comparison["validation.mean_return"].replay_mean == pytest.approx(1.0)


def test_reproduce_cli_requires_explicit_execute_compare_pair(tmp_path: Path) -> None:
    _training_run(tmp_path, "flag-contract")
    common = [
        "reproduce",
        "--run-id",
        "flag-contract",
        "--workspace-root",
        str(tmp_path),
        "--runs-root",
        "runs",
    ]

    incomplete = runner.invoke(app, [*common, "--execute"])
    conflicting = runner.invoke(
        app,
        [*common, "--verify-only", "--execute", "--compare"],
    )

    assert incomplete.exit_code == 2
    assert "--execute and --compare must be supplied together" in (
        incomplete.stdout + incomplete.stderr
    )
    assert conflicting.exit_code == 2
    assert "--verify-only cannot be combined" in (
        conflicting.stdout + conflicting.stderr
    )
