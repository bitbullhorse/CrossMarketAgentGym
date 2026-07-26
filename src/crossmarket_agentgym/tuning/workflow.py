"""End-to-end tuning workflow and locked validation-selected parameters."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from crossmarket_agentgym.rl.config import (
    TrainerConfig,
    TrainRunConfig,
    load_train_run_config,
)
from crossmarket_agentgym.rl.workflow import TrainingRunSummary, execute_training_run
from crossmarket_agentgym.tuning.config import TuningRunConfig
from crossmarket_agentgym.tuning.executors import LocalTrialExecutor, RayTrialExecutor
from crossmarket_agentgym.tuning.executors.base import ObjectiveEvaluator
from crossmarket_agentgym.tuning.factory import create_scheduler, create_searcher
from crossmarket_agentgym.tuning.models import TrialResult
from crossmarket_agentgym.tuning.objectives import select_trial
from crossmarket_agentgym.tuning.reports import write_study_report
from crossmarket_agentgym.tuning.rl_objective import PPOValidationObjective
from crossmarket_agentgym.tuning.runner import FunctionalObjective, TrialRunner
from crossmarket_agentgym.tuning.store import SQLiteStudyStore


class TuningRunSummary(BaseModel):
    """Serializable CLI result for a completed or resumed tuning study."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    study_name: str
    trial_count: int
    completed_count: int
    failed_count: int
    best_trial_id: int | None
    locked_parameters: dict[str, Any] | None
    storage_path: str
    report_json: str
    report_markdown: str
    retrain_checkpoint: str | None
    test_set_accessed: bool = False


def _benchmark(name: str) -> FunctionalObjective:
    def sphere(parameters: dict[str, Any]) -> float:
        return -sum(float(value) ** 2 for value in parameters.values())

    def rosenbrock(parameters: dict[str, Any]) -> float:
        values = [float(value) for value in parameters.values()]
        loss = sum(
            100.0 * (right - left * left) ** 2 + (1.0 - left) ** 2
            for left, right in zip(values, values[1:], strict=False)
        )
        return -loss

    return FunctionalObjective(sphere if name == "sphere" else rosenbrock)


def _create_objective(
    config: TuningRunConfig,
    run_dir: Path,
    base_train_config: TrainRunConfig | None = None,
) -> ObjectiveEvaluator:
    if config.objective.type in {"sphere", "rosenbrock"}:
        return _benchmark(config.objective.type)
    base_path = config.objective.base_train_config
    if base_path is None:
        raise ValueError("ppo_validation requires base_train_config")
    return PPOValidationObjective(
        base_config=(
            base_train_config
            if base_train_config is not None
            else load_train_run_config(base_path)
        ),
        objective_config=config.objective,
        output_dir=run_dir / "trials",
    )


def _create_executor(config: TuningRunConfig) -> LocalTrialExecutor | RayTrialExecutor:
    """Construct resource placement without altering search or scheduling."""
    if config.executor.type == "local":
        return LocalTrialExecutor()
    return RayTrialExecutor(
        address=config.executor.address,
        num_cpus_per_trial=config.executor.num_cpus_per_trial,
        num_gpus_per_trial=config.executor.num_gpus_per_trial,
        shutdown_on_close=config.executor.shutdown_on_close,
    )


def _independent_retrain(
    config: TuningRunConfig,
    best: TrialResult | None,
    run_dir: Path,
    base_train_config: TrainRunConfig | None = None,
) -> str | None:
    """Retrain locked PPO parameters from scratch without constructing test."""
    if (
        not config.retrain_locked
        or best is None
        or config.objective.type != "ppo_validation"
    ):
        return None
    base_path = config.objective.base_train_config
    if base_path is None:
        raise ValueError("ppo_validation requires base_train_config")
    base = (
        base_train_config
        if base_train_config is not None
        else load_train_run_config(base_path)
    )
    trainer_values = base.trainer.model_dump()
    trainer_values.update(best.parameters)
    trainer_values.update(
        seed=config.retrain_seed,
        total_timesteps=(
            config.retrain_timesteps
            if config.retrain_timesteps is not None
            else base.trainer.total_timesteps
        ),
        device=base.trainer.device,
    )
    retrain_identity = hashlib.sha256(
        json.dumps(
            trainer_values,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()[:12]
    retrain_run_name = (
        f"locked-retrain-t{best.trial_id:05d}-{retrain_identity}"
    )
    locked_config = base.model_copy(
        update={
            "output_dir": run_dir,
            "run_name": retrain_run_name,
            "trainer": TrainerConfig.model_validate(trainer_values),
        }
    )
    summary_path = run_dir / retrain_run_name / "run_summary.json"
    if summary_path.exists():
        summary = TrainingRunSummary.model_validate_json(
            summary_path.read_text(encoding="utf-8")
        )
    else:
        summary = execute_training_run(locked_config)
    return summary.checkpoint


def execute_tuning_run(
    config: TuningRunConfig,
    *,
    base_train_config: TrainRunConfig | None = None,
) -> TuningRunSummary:
    """Run/resume HPO using train+validation only and lock selected parameters."""
    run_dir = config.output_dir / config.study_name
    run_dir.mkdir(parents=True, exist_ok=True)
    searcher = create_searcher(config.searcher)
    scheduler = create_scheduler(
        config.scheduler,
        searcher_name=searcher.name,
        primary_direction=config.directions[0],
    )
    identity = {
        "directions": config.directions,
        "search_space": config.search_space.model_dump(mode="json"),
        "searcher": config.searcher.model_dump(mode="json"),
        "scheduler": config.scheduler.model_dump(mode="json"),
        "objective": config.objective.model_dump(mode="json"),
        "batch_size": config.batch_size,
    }
    if config.executor.type != "local":
        identity["executor"] = config.executor.model_dump(mode="json")
    config_fingerprint = hashlib.sha256(
        json.dumps(
            identity,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    executor = _create_executor(config)
    try:
        with SQLiteStudyStore(config.storage_path) as store:
            runner = TrialRunner(
                study_name=config.study_name,
                directions=config.directions,
                search_space=config.search_space,
                searcher=searcher,
                scheduler=scheduler,
                evaluator=_create_objective(config, run_dir, base_train_config),
                store=store,
                batch_size=config.batch_size,
                study_metadata={"config_sha256": config_fingerprint},
                executor=executor,
            )
            state = runner.run(config.max_trials)
    finally:
        executor.close()

    completed = [result for result in state.results if result.status == "completed"]
    best = select_trial(
        state.results,
        config.directions,
        strategy=config.selection.strategy,
        weights=config.selection.weights,
    )
    locked_parameters = None if best is None else dict(best.parameters)
    retrain_checkpoint = _independent_retrain(
        config,
        best,
        run_dir,
        base_train_config,
    )
    (run_dir / "locked_parameters.json").write_text(
        json.dumps(
            {
                "study_name": config.study_name,
                "selected_on": "validation",
                "test_set_accessed": False,
                "trial_id": None if best is None else best.trial_id,
                "parameters": locked_parameters,
                "independent_retrain_checkpoint": retrain_checkpoint,
            },
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "resolved_tuning_config.json").write_text(
        config.model_dump_json(indent=2),
        encoding="utf-8",
    )
    report_json, report_markdown = write_study_report(state, run_dir)
    summary = TuningRunSummary(
        study_name=config.study_name,
        trial_count=len(state.results),
        completed_count=len(completed),
        failed_count=sum(result.status == "failed" for result in state.results),
        best_trial_id=None if best is None else best.trial_id,
        locked_parameters=locked_parameters,
        storage_path=str(config.storage_path),
        report_json=str(report_json),
        report_markdown=str(report_markdown),
        retrain_checkpoint=retrain_checkpoint,
    )
    (run_dir / "tuning_summary.json").write_text(
        summary.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return summary
