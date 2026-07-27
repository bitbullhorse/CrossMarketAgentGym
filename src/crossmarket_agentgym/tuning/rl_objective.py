"""Partition-safe PPO objective evaluated only on validation data."""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

import numpy as np

from crossmarket_agentgym.environments import CrossMarketPortfolioEnv
from crossmarket_agentgym.evaluation import EvaluationResult, evaluate_policy
from crossmarket_agentgym.rl.callbacks import build_callbacks
from crossmarket_agentgym.rl.config import (
    TemporalSplitConfig,
    TrainerConfig,
    TrainRunConfig,
)
from crossmarket_agentgym.rl.trainers import trainer_from_config
from crossmarket_agentgym.rl.workflow import build_partitioned_environments
from crossmarket_agentgym.tuning.config import ObjectiveConfig
from crossmarket_agentgym.tuning.models import TrialResult, TrialSuggestion
from crossmarket_agentgym.tuning.objectives import (
    ValidationRecord,
    multi_objective_values,
    robust_portfolio_score,
    seed_sharpe_instability,
)


def _validation_sharpe(result: EvaluationResult, initial_cash: float) -> float:
    """Calculate a finite annualized Sharpe from audited validation equity steps."""
    returns: list[float] = []
    previous_by_episode: dict[int, float] = {}
    for weight in result.weights:
        previous = previous_by_episode.get(weight.episode, initial_cash)
        returns.append(weight.portfolio_value / previous - 1.0)
        previous_by_episode[weight.episode] = weight.portfolio_value
    if not returns:
        return 0.0
    mean = float(np.mean(returns))
    deviation = float(np.std(returns, ddof=0))
    sharpe = mean * math.sqrt(252.0) if deviation <= 1e-12 else (
        mean / deviation * math.sqrt(252.0)
    )
    return float(np.clip(sharpe, -1_000.0, 1_000.0))


class PPOValidationObjective:
    """Train on train capabilities and score on validation capabilities."""

    def __init__(
        self,
        *,
        base_config: TrainRunConfig,
        objective_config: ObjectiveConfig,
        output_dir: Path,
        fold_splits: tuple[TemporalSplitConfig, ...] | None = None,
    ) -> None:
        if base_config.trainer.algorithm != "PPO":
            raise ValueError("ppo_validation objective requires a PPO base config")
        self.base_config = base_config
        self.objective_config = objective_config
        self.output_dir = output_dir
        if fold_splits is not None:
            if len(fold_splits) != objective_config.walk_forward_folds:
                raise ValueError("explicit fold count differs from objective configuration")
            if any(split.test_end_execution_index is not None for split in fold_splits):
                raise ValueError("HPO fold splits cannot expose a test partition")
        self.fold_splits = fold_splits

    def _build_environments(
        self,
        trial_config: TrainRunConfig,
        fold: int,
    ) -> dict[str, CrossMarketPortfolioEnv]:
        """Build train/validation environments without test access."""
        del fold
        return build_partitioned_environments(
            trial_config,
            include_test=False,
        )

    def _trainer_config(
        self,
        parameters: dict[str, Any],
        seed: int,
    ) -> TrainerConfig:
        raw = self.base_config.trainer.model_dump()
        raw.update(parameters)
        raw.update(
            total_timesteps=self.objective_config.total_timesteps,
            seed=seed,
            device="cpu",
        )
        return TrainerConfig.model_validate(raw)

    def _fold_config(
        self,
        trainer_config: TrainerConfig,
        fold: int,
    ) -> TrainRunConfig:
        """Build an expanding-train, forward-validation split without test."""
        if self.fold_splits is not None:
            return self.base_config.model_copy(
                update={
                    "trainer": trainer_config,
                    "split": self.fold_splits[fold],
                }
            )
        base_split = self.base_config.split
        validation_width = (
            base_split.validation_end_execution_index
            - base_split.train_end_execution_index
        )
        stride = self.objective_config.walk_forward_stride or validation_width
        shift = fold * stride
        split = TemporalSplitConfig(
            train_end_execution_index=base_split.train_end_execution_index + shift,
            validation_end_execution_index=(
                base_split.validation_end_execution_index + shift
            ),
            test_end_execution_index=None,
        )
        return self.base_config.model_copy(
            update={"trainer": trainer_config, "split": split}
        )

    def evaluate(self, suggestion: TrialSuggestion) -> TrialResult:
        """Evaluate all configured seeds without ever constructing test data."""
        records: list[ValidationRecord] = []
        for fold in range(self.objective_config.walk_forward_folds):
            for seed in self.objective_config.seeds:
                trainer_config = self._trainer_config(suggestion.parameters, seed)
                trial_config = self._fold_config(trainer_config, fold)
                environments = self._build_environments(trial_config, fold)
                if set(environments) != {"train", "validation"}:
                    raise PermissionError("HPO objective received a forbidden partition")
                run_dir = (
                    self.output_dir
                    / f"trial_{suggestion.trial_id:05d}"
                    / f"fold_{fold:03d}"
                    / f"seed_{seed:010d}"
                )
                trainer = trainer_from_config(trainer_config, run_dir)
                checkpoint = run_dir / "checkpoints" / "final_model.zip"
                started = perf_counter()
                if checkpoint.exists():
                    model = trainer.load(checkpoint, environments["train"])
                else:
                    callbacks, _ = build_callbacks(
                        trial_config.callbacks,
                        trainer_config,
                        run_dir,
                        validation_env=environments["validation"],
                    )
                    artifact = trainer.train(
                        environments["train"],
                        trainer_config,
                        callbacks,
                    )
                    model = artifact.model
                validation = evaluate_policy(
                    environments["validation"],
                    model,
                    algorithm=trainer_config.algorithm,
                    episodes=trainer_config.eval_episodes,
                    deterministic=trainer_config.deterministic_eval,
                    seed=seed,
                )
                elapsed = perf_counter() - started
                if validation.partition != "validation":
                    raise PermissionError("HPO objective may only score validation data")
                record = ValidationRecord(
                    seed=seed,
                    fold=fold,
                    sharpe=_validation_sharpe(
                        validation,
                        trial_config.environment.initial_cash,
                    ),
                    max_drawdown=validation.metrics["max_drawdown"],
                    turnover=validation.metrics["mean_turnover"],
                    training_seconds=elapsed,
                )
                records.append(record)
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "hpo_validation.json").write_text(
                    json.dumps(
                        {
                            "partition": "validation",
                            "record": record.model_dump(mode="json"),
                            "test_access": False,
                        },
                        allow_nan=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )

        objectives = (
            multi_objective_values(
                records,
                include_training_time=self.objective_config.include_training_time,
            )
            if self.objective_config.mode == "multi_objective"
            else (robust_portfolio_score(records),)
        )
        sharpes = [record.sharpe for record in records]
        return TrialResult(
            trial_id=suggestion.trial_id,
            parameters=suggestion.parameters,
            status="completed",
            objectives=objectives,
            metrics={
                "validation_median_sharpe": float(median(sharpes)),
                "validation_median_max_drawdown": float(
                    median(record.max_drawdown for record in records)
                ),
                "validation_median_turnover": float(
                    median(record.turnover for record in records)
                ),
                "validation_sharpe_instability": seed_sharpe_instability(records),
                "validation_seed_count": float(len(self.objective_config.seeds)),
                "validation_fold_count": float(
                    self.objective_config.walk_forward_folds
                ),
            },
            resource=float(self.objective_config.total_timesteps * len(records)),
        )
