from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from crossmarket_agentgym.agents.config import load_agent_runtime_config
from crossmarket_agentgym.agents.layer_config import load_phase7_run_config
from crossmarket_agentgym.agents.layer_stack import execute_phase7_stack
from crossmarket_agentgym.agents.runtime_workflow import execute_agent_runtime
from crossmarket_agentgym.cli.app import app
from crossmarket_agentgym.release import reproduce_run
from crossmarket_agentgym.rl.artifacts import TrainingMetadata
from crossmarket_agentgym.rl.config import load_train_run_config
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
        ],
    )
    assert result.exit_code == 0
    assert '"is_valid": true' in result.stdout
    assert '"network_used": false' in result.stdout
