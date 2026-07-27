"""Phase 12 Group F equal-budget, test-isolated HPO experiments."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from crossmarket_agentgym.environments import CrossMarketPortfolioEnv
from crossmarket_agentgym.experiments.metrics import formal_portfolio_metrics
from crossmarket_agentgym.experiments.models import FormalExperimentProtocol
from crossmarket_agentgym.experiments.strategy_runs import formal_train_config
from crossmarket_agentgym.experiments.training import (
    build_formal_partitioned_environments,
    execute_formal_training_run,
)
from crossmarket_agentgym.rl.config import TemporalSplitConfig, TrainerConfig
from crossmarket_agentgym.rl.workflow import evaluate_saved_run
from crossmarket_agentgym.tuning.config import (
    ObjectiveConfig,
    SchedulerConfig,
    SearcherConfig,
)
from crossmarket_agentgym.tuning.executors import LocalTrialExecutor
from crossmarket_agentgym.tuning.factory import create_scheduler, create_searcher
from crossmarket_agentgym.tuning.models import (
    ParameterSpec,
    SearchSpace,
    StudyState,
    TrialResult,
    TrialSuggestion,
)
from crossmarket_agentgym.tuning.objectives import (
    default_multi_objective_directions,
    pareto_front,
    select_trial,
)
from crossmarket_agentgym.tuning.reports import write_study_report
from crossmarket_agentgym.tuning.rl_objective import PPOValidationObjective
from crossmarket_agentgym.tuning.runner import TrialRunner
from crossmarket_agentgym.tuning.store import SQLiteStudyStore


class _FormalPPOValidationObjective(PPOValidationObjective):
    """Apply frozen Phase 12 fold starts without changing the public HPO API."""

    def __init__(
        self,
        *,
        protocol: FormalExperimentProtocol,
        base_config: Any,
        objective_config: ObjectiveConfig,
        output_dir: Path,
        fold_splits: tuple[TemporalSplitConfig, ...],
    ) -> None:
        super().__init__(
            base_config=base_config,
            objective_config=objective_config,
            output_dir=output_dir,
            fold_splits=fold_splits,
        )
        self._protocol = protocol

    def _trainer_config(
        self,
        parameters: dict[str, Any],
        seed: int,
    ) -> TrainerConfig:
        config = super()._trainer_config(parameters, seed)
        return config.model_copy(update={"device": "auto"})

    def _build_environments(
        self,
        trial_config: Any,
        fold: int,
    ) -> dict[str, CrossMarketPortfolioEnv]:
        return build_formal_partitioned_environments(
            self._protocol,
            trial_config,
            train_start=self._protocol.partitions.walk_forward[fold].train.start,
            include_test=False,
        )


def _space(protocol: FormalExperimentProtocol) -> SearchSpace:
    parameters = []
    for name, specification in protocol.drl.search_space.items():
        parameters.append(ParameterSpec.model_validate({"name": name, **specification}))
    return SearchSpace(
        parameters=tuple(parameters),
        constraints=("batch_size <= n_steps",),
    )


def _folds(
    protocol: FormalExperimentProtocol,
    *,
    workspace_root: Path,
    seed: int,
) -> tuple[TemporalSplitConfig, ...]:
    context = formal_train_config(
        protocol,
        workspace_root=workspace_root,
        run_name="fold_context",
        output_dir=workspace_root / "results",
        algorithm="PPO",
        seed=seed,
        total_timesteps=1,
    )
    from crossmarket_agentgym.environments import MarketDataPanel

    panel = MarketDataPanel.from_manifest(context.dataset_root)

    def boundary(value: Any) -> int:
        candidates = [index for index, day in enumerate(panel.dates) if day <= value]
        if not candidates:
            raise ValueError(f"walk-forward boundary precedes dataset: {value}")
        return candidates[-1]

    return tuple(
        TemporalSplitConfig(
            train_end_execution_index=boundary(fold.train.end),
            validation_end_execution_index=boundary(fold.validation.end),
            test_end_execution_index=None,
        )
        for fold in protocol.partitions.walk_forward
    )


def _objective(
    protocol: FormalExperimentProtocol,
    *,
    workspace_root: Path,
    seed: int,
    output_dir: Path,
    multi_objective: bool,
) -> tuple[PPOValidationObjective, Any]:
    base = formal_train_config(
        protocol,
        workspace_root=workspace_root,
        run_name="hpo_base",
        output_dir=output_dir,
        algorithm="PPO",
        seed=seed,
        total_timesteps=protocol.hpo.timesteps_per_trial,
    )
    objective_config = ObjectiveConfig(
        type="ppo_validation",
        base_train_config=Path(
            f"experiments/{protocol.protocol_id.replace('-', '_')}.yaml"
        ),
        budget_stage="stage_a",
        seeds=(seed,),
        walk_forward_folds=protocol.hpo.walk_forward_folds,
        total_timesteps=protocol.hpo.timesteps_per_trial,
        mode="multi_objective" if multi_objective else "robust",
        include_training_time=False,
    )
    return (
        _FormalPPOValidationObjective(
            protocol=protocol,
            base_config=base,
            objective_config=objective_config,
            output_dir=output_dir / "trials",
            fold_splits=_folds(protocol, workspace_root=workspace_root, seed=seed),
        ),
        base,
    )


def _default_parameters() -> dict[str, Any]:
    return {
        "learning_rate": 3e-4,
        "gamma": 0.99,
        "n_steps": 256,
        "batch_size": 64,
    }


def _run_search(
    *,
    protocol: FormalExperimentProtocol,
    method: str,
    seed: int,
    run_dir: Path,
    objective: PPOValidationObjective,
) -> tuple[StudyState, tuple[str, ...]]:
    if method == "default":
        results = tuple(
            objective.evaluate(
                TrialSuggestion(
                    trial_id=trial_id,
                    parameters=_default_parameters(),
                )
            )
            for trial_id in range(protocol.hpo.trials_per_searcher)
        )
        return (
            StudyState(
                study_name=f"phase12-{method}-s{seed}",
                directions=("maximize",),
                results=results,
            ),
            (),
        )
    searcher = create_searcher(
        SearcherConfig(
            type=method,  # type: ignore[arg-type]
            seed=seed,
            population_size=8,
            startup_trials=8,
            candidate_count=32,
        )
    )
    directions = (
        default_multi_objective_directions()
        if method == "nsga_ii"
        else ("maximize",)
    )
    maximum_resource = float(
        protocol.hpo.timesteps_per_trial
        * protocol.hpo.walk_forward_folds
    )
    scheduler = create_scheduler(
        SchedulerConfig(
            type=protocol.hpo.scheduler,
            direction=directions[0],
            grace_period=maximum_resource / 9.0,
            min_resource=maximum_resource / 9.0,
            max_resource=maximum_resource,
            reduction_factor=3,
        ),
        searcher_name=searcher.name,
        primary_direction=directions[0],
    )
    study_name = f"phase12-{method}-s{seed}"
    database = run_dir / "study.sqlite3"
    with SQLiteStudyStore(database) as store:
        runner = TrialRunner(
            study_name=study_name,
            directions=directions,
            search_space=_space(protocol),
            searcher=searcher,
            scheduler=scheduler,
            evaluator=objective,
            store=store,
            batch_size=1,
            study_metadata={
                "formal": True,
                "scheduler_role": "resource_only",
                "test_partition_visible": False,
            },
            executor=LocalTrialExecutor(),
        )
        state = runner.run(protocol.hpo.trials_per_searcher)
    return state, (scheduler.name,)


def _locked_test(
    *,
    protocol: FormalExperimentProtocol,
    workspace_root: Path,
    task_seed: int,
    parameters: dict[str, Any],
    run_dir: Path,
) -> tuple[dict[str, float], dict[str, Any]]:
    retrain_seed = 1_000_000 + task_seed
    base = formal_train_config(
        protocol,
        workspace_root=workspace_root,
        run_name="locked_retrain",
        output_dir=run_dir,
        algorithm="PPO",
        seed=retrain_seed,
    )
    raw = base.trainer.model_dump()
    raw.update(parameters)
    raw.update(
        seed=retrain_seed,
        total_timesteps=protocol.drl.total_timesteps,
    )
    locked = base.model_copy(
        update={"trainer": TrainerConfig.model_validate(raw)}
    )
    summary = execute_formal_training_run(protocol, locked)
    lock = {
        "selected_on": "walk_forward_validation",
        "test_metrics_accessed": False,
        "parameters": parameters,
        "search_seed": task_seed,
        "independent_retrain_seed": retrain_seed,
        "configuration_source": "frozen_protocol_and_completed_validation_trials",
    }
    (run_dir / "configuration_lock.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    test = evaluate_saved_run(Path(summary.run_dir), partition="test")
    return formal_portfolio_metrics(test), {
        "trained_timesteps": summary.trained_timesteps,
        "independent_retrain_seed": retrain_seed,
        "test_evaluation_count": 1,
    }


def run_group_f(
    *,
    protocol: FormalExperimentProtocol,
    workspace_root: Path,
    method: str,
    seed: int,
    run_dir: Path,
) -> dict[str, Any]:
    """Run equal-budget validation search, lock once, and evaluate test once."""
    run_dir.mkdir(parents=True, exist_ok=True)
    multi = method == "nsga_ii"
    objective, _ = _objective(
        protocol,
        workspace_root=workspace_root,
        seed=seed,
        output_dir=run_dir,
        multi_objective=multi,
    )
    started = time.perf_counter()
    state, scheduler_names = _run_search(
        protocol=protocol,
        method=method,
        seed=seed,
        run_dir=run_dir,
        objective=objective,
    )
    completed = [result for result in state.results if result.status == "completed"]
    if not completed:
        raise RuntimeError("HPO produced no completed validation Trial")
    selection = "pareto_first" if multi else "primary"
    best = select_trial(
        completed,
        state.directions,
        strategy=selection,
    )
    if best is None:
        raise RuntimeError("HPO could not lock a completed Trial")
    report_json, report_markdown = write_study_report(state, run_dir)
    test_metrics, retrain = _locked_test(
        protocol=protocol,
        workspace_root=workspace_root,
        task_seed=seed,
        parameters=dict(best.parameters),
        run_dir=run_dir / "locked",
    )
    runtime = time.perf_counter() - started
    validation_sharpe = float(best.metrics.get("validation_median_sharpe", 0.0))
    front: list[TrialResult] = (
        pareto_front(completed, state.directions) if multi else []
    )
    return {
        "method": method,
        "seed": seed,
        "validation_score": best.objectives[0],
        "validation_median_sharpe": validation_sharpe,
        "locked_test_score": test_metrics["sharpe"],
        "locked_test_metrics": test_metrics,
        "convergence": [
            {
                "trial_id": result.trial_id,
                "objectives": list(result.objectives),
                "status": result.status,
            }
            for result in state.results
        ],
        "runtime_seconds": runtime,
        "stability": best.metrics.get("validation_sharpe_instability", 0.0),
        "pareto_front": [
            {
                "trial_id": result.trial_id,
                "parameters": result.parameters,
                "objectives": list(result.objectives),
            }
            for result in front
        ],
        "tuning_overfit_gap": validation_sharpe - test_metrics["sharpe"],
        "trial_budget": protocol.hpo.trials_per_searcher,
        "timesteps_per_trial": protocol.hpo.timesteps_per_trial,
        "walk_forward_folds": protocol.hpo.walk_forward_folds,
        "objective_seeds": [seed],
        "scheduler": list(scheduler_names),
        "scheduler_role": "resource_only",
        "test_partition_visible_during_search": False,
        "report_json": report_json.as_posix(),
        "report_markdown": report_markdown.as_posix(),
        **retrain,
    }
