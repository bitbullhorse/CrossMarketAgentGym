"""Phase 12-private chronological training boundary and execution helpers."""

from __future__ import annotations

import platform
import time
from datetime import UTC, date, datetime
from pathlib import Path

import torch

from crossmarket_agentgym.audit.run_manifest import write_run_manifest
from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.data.partitions import PartitionCapability
from crossmarket_agentgym.environments import (
    CrossMarketPortfolioEnv,
    MarketDataPanel,
)
from crossmarket_agentgym.evaluation import (
    evaluate_policy,
    write_evaluation_artifacts,
)
from crossmarket_agentgym.experiments.models import FormalExperimentProtocol
from crossmarket_agentgym.rl.callbacks import build_callbacks
from crossmarket_agentgym.rl.config import TrainRunConfig
from crossmarket_agentgym.rl.trainers import trainer_from_config
from crossmarket_agentgym.rl.workflow import TrainingRunSummary


def formal_train_start_signal_index(
    panel: MarketDataPanel,
    *,
    train_start: date,
    lookback: int,
) -> int:
    """Return the last signal before the first authorized training outcome."""
    candidates = [
        index for index, value in enumerate(panel.dates) if value < train_start
    ]
    if not candidates:
        raise ValueError(f"dataset has no signal session before {train_start}")
    signal = candidates[-1]
    minimum = max(lookback - 1, panel.first_fully_valued_index)
    if signal < minimum:
        raise ValueError(
            "formal training start precedes leakage-safe lookback/valuation history"
        )
    return signal


def build_formal_partitioned_environments(
    protocol: FormalExperimentProtocol,
    config: TrainRunConfig,
    *,
    train_start: date | None = None,
    include_test: bool = True,
) -> dict[str, CrossMarketPortfolioEnv]:
    """Build Phase 12 partitions with an explicit first training outcome date."""
    panel = MarketDataPanel.from_manifest(
        config.dataset_root,
        base_currency=config.environment.base_currency,
    )
    dataset_id = sha256_file(config.dataset_root / "dataset_manifest.json")
    start_signal = formal_train_start_signal_index(
        panel,
        train_start=train_start or protocol.partitions.train.start,
        lookback=config.environment.lookback,
    )
    split = config.split
    final_boundary = (
        split.test_end_execution_index
        if split.test_end_execution_index is not None
        else split.validation_end_execution_index
    )
    if start_signal >= split.train_end_execution_index:
        raise ValueError("formal training interval is empty")
    if final_boundary >= panel.session_count:
        raise ValueError("formal split boundary exceeds available sessions")

    def environment(
        partition: str,
        signal_index: int,
        execution_end: int,
    ) -> CrossMarketPortfolioEnv:
        context_start = max(
            0,
            signal_index - config.environment.lookback + 1,
        )
        isolated = panel.slice_sessions(context_start, execution_end)
        return CrossMarketPortfolioEnv(
            isolated,
            config.environment,
            observation=config.observation,
            partition=PartitionCapability(
                dataset_id=dataset_id,
                partition=partition,  # type: ignore[arg-type]
                start_signal_index=signal_index - context_start,
                end_execution_index=execution_end - context_start,
            ),
        )

    environments = {
        "train": environment(
            "train",
            start_signal,
            split.train_end_execution_index,
        ),
        "validation": environment(
            "validation",
            split.train_end_execution_index,
            split.validation_end_execution_index,
        ),
    }
    if include_test and split.test_end_execution_index is not None:
        environments["test"] = environment(
            "test",
            split.validation_end_execution_index,
            split.test_end_execution_index,
        )
    return environments


def execute_formal_training_run(
    protocol: FormalExperimentProtocol,
    config: TrainRunConfig,
    *,
    train_start: date | None = None,
) -> TrainingRunSummary:
    """Train with Phase 12's private start boundary and validation-only selection."""
    started_at = datetime.now(UTC)
    overall_start = time.perf_counter()
    run_dir = config.output_dir / config.run_name
    if (run_dir / "training_artifact.json").exists():
        raise FileExistsError(f"run already exists: {run_dir}")
    environments = build_formal_partitioned_environments(
        protocol,
        config,
        train_start=train_start,
        include_test=False,
    )
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
        runtime_seconds=time.perf_counter() - overall_start,
        training_runtime_seconds=training_runtime,
        evaluation_runtime_seconds=evaluation_runtime,
        device=str(artifact.model.device),
        torch_version=torch.__version__,
        python_version=platform.python_version(),
        cpu_model=platform.processor().strip() or platform.machine() or "unknown",
        gpu_model=(
            torch.cuda.get_device_name(torch.cuda.current_device())
            if torch.cuda.is_available()
            else None
        ),
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
        dataset_sha256=sha256_file(
            config.dataset_root / "dataset_manifest.json"
        ),
        seed=config.trainer.seed,
    )
    return summary
