"""End-to-end partitioned training and locked evaluation workflows."""

from __future__ import annotations

import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import torch
from pydantic import BaseModel, ConfigDict

from crossmarket_agentgym.audit import write_run_manifest
from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.data.partitions import PartitionCapability
from crossmarket_agentgym.environments import CrossMarketPortfolioEnv, MarketDataPanel
from crossmarket_agentgym.evaluation import (
    EvaluationResult,
    evaluate_policy,
    write_evaluation_artifacts,
)
from crossmarket_agentgym.rl.callbacks import build_callbacks
from crossmarket_agentgym.rl.config import TrainRunConfig
from crossmarket_agentgym.rl.trainers import trainer_from_config


class TrainingRunSummary(BaseModel):
    """Serializable CLI result for a completed training run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    run_dir: str
    algorithm: str
    checkpoint: str
    requested_timesteps: int
    trained_timesteps: int
    validation_metrics: dict[str, float]
    started_at: datetime
    finished_at: datetime
    runtime_seconds: float
    training_runtime_seconds: float
    evaluation_runtime_seconds: float
    device: str
    torch_version: str
    python_version: str
    cpu_model: str
    gpu_model: str | None


def build_partitioned_environments(
    config: TrainRunConfig,
    *,
    include_test: bool = True,
) -> dict[str, CrossMarketPortfolioEnv]:
    """Build disjoint outcome intervals over one verified market panel."""
    panel = MarketDataPanel.from_manifest(
        config.dataset_root,
        base_currency=config.environment.base_currency,
    )
    dataset_id = sha256_file(config.dataset_root / "dataset_manifest.json")
    safe_start = max(
        config.environment.lookback - 1,
        panel.first_fully_valued_index,
    )
    split = config.split
    final_boundary = (
        split.test_end_execution_index
        if split.test_end_execution_index is not None
        else split.validation_end_execution_index
    )
    if final_boundary >= panel.session_count:
        raise ValueError("split boundary exceeds available panel sessions")
    def partition_environment(
        partition: Literal["train", "validation", "test"],
        signal_index: int,
        execution_end: int,
    ) -> CrossMarketPortfolioEnv:
        context_start = max(0, signal_index - config.environment.lookback + 1)
        isolated_panel = panel.slice_sessions(context_start, execution_end)
        local_signal = signal_index - context_start
        local_end = execution_end - context_start
        return CrossMarketPortfolioEnv(
            isolated_panel,
            config.environment,
            observation=config.observation,
            partition=PartitionCapability(
                dataset_id=dataset_id,
                partition=partition,
                start_signal_index=local_signal,
                end_execution_index=local_end,
            ),
        )

    environments = {
        "train": partition_environment(
            "train",
            safe_start,
            split.train_end_execution_index,
        ),
        "validation": partition_environment(
            "validation",
            split.train_end_execution_index,
            split.validation_end_execution_index,
        ),
    }
    if include_test and split.test_end_execution_index is not None:
        environments["test"] = partition_environment(
            "test",
            split.validation_end_execution_index,
            split.test_end_execution_index,
        )
    return environments


def execute_training_run(config: TrainRunConfig) -> TrainingRunSummary:
    """Train on train, select on validation, and never read test."""
    started_at = datetime.now(UTC)
    overall_start = time.perf_counter()
    run_dir = config.output_dir / config.run_name
    if (run_dir / "training_artifact.json").exists():
        raise FileExistsError(f"run already exists: {run_dir}")
    environments = build_partitioned_environments(config, include_test=False)
    trainer = trainer_from_config(config.trainer, run_dir)
    callbacks, _ = build_callbacks(
        config.callbacks,
        config.trainer,
        run_dir,
        validation_env=environments["validation"],
    )
    training_start = time.perf_counter()
    artifact = trainer.train(environments["train"], config.trainer, callbacks)
    training_runtime = time.perf_counter() - training_start
    evaluation_start = time.perf_counter()
    validation = evaluate_policy(
        environments["validation"],
        artifact.model,
        algorithm=config.trainer.algorithm,
        episodes=config.trainer.eval_episodes,
        deterministic=config.trainer.deterministic_eval,
        seed=config.trainer.seed,
    )
    evaluation_runtime = time.perf_counter() - evaluation_start
    write_evaluation_artifacts(validation, run_dir / "validation")
    (run_dir / "resolved_config.json").write_text(
        config.model_dump_json(indent=2),
        encoding="utf-8",
    )
    finished_at = datetime.now(UTC)
    runtime_seconds = time.perf_counter() - overall_start
    cpu_model = platform.processor().strip() or platform.machine() or "unknown"
    device = str(artifact.model.device)
    gpu_model = (
        torch.cuda.get_device_name(artifact.model.device)
        if device.startswith("cuda") and torch.cuda.is_available()
        else None
    )
    summary = TrainingRunSummary(
        run_id=config.run_name,
        run_dir=str(run_dir),
        algorithm=config.trainer.algorithm,
        checkpoint=str(artifact.checkpoint_path),
        requested_timesteps=artifact.metadata.requested_timesteps,
        trained_timesteps=artifact.metadata.trained_timesteps,
        validation_metrics=validation.metrics,
        started_at=started_at,
        finished_at=finished_at,
        runtime_seconds=runtime_seconds,
        training_runtime_seconds=training_runtime,
        evaluation_runtime_seconds=evaluation_runtime,
        device=device,
        torch_version=torch.__version__,
        python_version=platform.python_version(),
        cpu_model=cpu_model,
        gpu_model=gpu_model,
    )
    (run_dir / "run_summary.json").write_text(
        summary.model_dump_json(indent=2),
        encoding="utf-8",
    )
    write_run_manifest(
        run_dir,
        workspace_root=Path.cwd(),
        run_id=config.run_name,
        kind="training",
        config_path=run_dir / "resolved_config.json",
        dataset_sha256=sha256_file(config.dataset_root / "dataset_manifest.json"),
        seed=config.trainer.seed,
    )
    return summary


def evaluate_saved_run(
    run_dir: Path,
    *,
    partition: Literal["validation", "test"] = "test",
    config_override: TrainRunConfig | None = None,
) -> EvaluationResult:
    """Evaluate a saved checkpoint once on validation or locked test data."""
    return _evaluate_saved_run(
        run_dir,
        partition=partition,
        config_override=config_override,
        output_dir_override=None,
    )


def _evaluate_saved_run(
    run_dir: Path,
    *,
    partition: Literal["validation", "test"],
    config_override: TrainRunConfig | None,
    output_dir_override: Path | None,
) -> EvaluationResult:
    """Shared implementation for public evaluation and isolated GUI backtests."""
    if output_dir_override is not None and partition == "test":
        raise ValueError("locked test evaluation must remain inside the source run")
    config_path = run_dir / "resolved_config.json"
    if config_override is None and not config_path.exists():
        raise FileNotFoundError(config_path)
    config = (
        config_override
        if config_override is not None
        else TrainRunConfig.model_validate_json(
            config_path.read_text(encoding="utf-8")
        )
    )
    environments = build_partitioned_environments(config)
    if partition not in environments:
        raise ValueError(f"run has no {partition} partition")
    output_dir = output_dir_override or run_dir / partition
    if partition == "test" and (output_dir / "metrics.json").exists():
        raise FileExistsError("locked test evaluation already exists")
    if output_dir_override is not None and output_dir.exists():
        raise FileExistsError("independent validation backtest already exists")
    trainer = trainer_from_config(config.trainer, run_dir)
    checkpoint = run_dir / "checkpoints" / "final_model.zip"
    result = trainer.evaluate(
        environments[partition],
        checkpoint,
        episodes=config.trainer.eval_episodes,
    )
    write_evaluation_artifacts(result, output_dir)
    if output_dir_override is not None:
        (output_dir / "source_run.json").write_text(
            json.dumps(
                {
                    "source_run_id": config.run_name,
                    "source_run_path": run_dir.as_posix(),
                    "partition": partition,
                    "selection_authority": False,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    if output_dir_override is None and config_path.is_file():
        write_run_manifest(
            run_dir,
            workspace_root=Path.cwd(),
            run_id=config.run_name,
            kind="training",
            config_path=config_path,
            dataset_sha256=sha256_file(
                config.dataset_root / "dataset_manifest.json"
            ),
            seed=config.trainer.seed,
        )
    return result
