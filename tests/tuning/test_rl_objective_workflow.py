from __future__ import annotations

from pathlib import Path

from crossmarket_agentgym.rl import CallbackConfig, load_train_run_config
from crossmarket_agentgym.tuning.config import (
    ObjectiveConfig,
    SchedulerConfig,
    SearcherConfig,
    TuningRunConfig,
)
from crossmarket_agentgym.tuning.models import ParameterSpec, SearchSpace, TrialSuggestion
from crossmarket_agentgym.tuning.rl_objective import PPOValidationObjective
from crossmarket_agentgym.tuning.workflow import execute_tuning_run


def test_ppo_objective_trains_on_train_and_scores_validation_only(
    tmp_path: Path,
) -> None:
    base = load_train_run_config(Path("configs/train/ppo.yaml"))
    base = base.model_copy(
        update={
            "callbacks": CallbackConfig(
                checkpoint_freq=0,
                validation_freq=0,
                early_stop_patience=0,
                resource_monitor_freq=0,
                audit_freq=0,
                metrics_freq=0,
            )
        }
    )
    objective = PPOValidationObjective(
        base_config=base,
        objective_config=ObjectiveConfig(
            type="ppo_validation",
            base_train_config=Path("configs/train/ppo.yaml"),
            budget_stage="stage_a",
            seeds=(41,),
            walk_forward_folds=1,
            total_timesteps=8,
        ),
        output_dir=tmp_path,
    )
    first_fold = objective._fold_config(  # noqa: SLF001 - fold contract test
        objective._trainer_config({}, 41),  # noqa: SLF001
        1,
    )
    assert first_fold.split.train_end_execution_index == 3
    assert first_fold.split.validation_end_execution_index == 4
    assert first_fold.split.test_end_execution_index is None
    result = objective.evaluate(
        TrialSuggestion(
            trial_id=0,
            parameters={
                "n_steps": 4,
                "batch_size": 2,
                "n_epochs": 1,
                "features_dim": 16,
            },
        )
    )

    assert result.status == "completed"
    assert result.resource == 8
    assert set(result.metrics) == {
        "validation_median_sharpe",
        "validation_median_max_drawdown",
        "validation_median_turnover",
        "validation_sharpe_instability",
        "validation_seed_count",
        "validation_fold_count",
    }
    audit = (
        tmp_path
        / "trial_00000"
        / "fold_000"
        / "seed_0000000041"
        / "hpo_validation.json"
    )
    assert '"partition": "validation"' in audit.read_text(encoding="utf-8")
    assert not list(tmp_path.rglob("*test*"))


def test_pso_four_by_two_cpu_study_is_resumable(tmp_path: Path) -> None:
    config = TuningRunConfig(
        study_name="pso-4x2",
        output_dir=tmp_path / "runs",
        storage_path=tmp_path / "study.sqlite3",
        max_trials=8,
        batch_size=4,
        search_space=SearchSpace(
            parameters=(
                ParameterSpec(name="x", kind="float", low=-2.0, high=2.0),
                ParameterSpec(name="y", kind="float", low=-2.0, high=2.0),
            )
        ),
        searcher=SearcherConfig(type="pso", seed=5, population_size=4),
        scheduler=SchedulerConfig(type="fifo"),
        objective=ObjectiveConfig(type="sphere"),
    )
    first = execute_tuning_run(config)
    resumed = execute_tuning_run(config)

    assert first.trial_count == 8
    assert first.completed_count == 8
    assert first.failed_count == 0
    assert resumed == first
    assert first.best_trial_id is not None
    assert first.test_set_accessed is False
    assert Path(first.report_json).exists()


def test_locked_ppo_parameters_are_independently_retrained_without_test(
    tmp_path: Path,
) -> None:
    config = TuningRunConfig(
        study_name="locked-retrain",
        output_dir=tmp_path / "runs",
        storage_path=tmp_path / "study.sqlite3",
        max_trials=1,
        search_space=SearchSpace(
            parameters=(
                ParameterSpec(
                    name="learning_rate",
                    kind="float",
                    low=1.0e-4,
                    high=1.0e-3,
                    log=True,
                ),
            )
        ),
        searcher=SearcherConfig(type="random", seed=5),
        scheduler=SchedulerConfig(type="fifo"),
        objective=ObjectiveConfig(
            type="ppo_validation",
            base_train_config=Path("configs/train/ppo_tune_smoke.yaml"),
            budget_stage="stage_a",
            seeds=(11,),
            walk_forward_folds=1,
            total_timesteps=4,
        ),
        retrain_locked=True,
        retrain_seed=77,
        retrain_timesteps=4,
    )
    summary = execute_tuning_run(config)

    assert summary.retrain_checkpoint is not None
    checkpoint = Path(summary.retrain_checkpoint)
    assert checkpoint.exists()
    resolved = checkpoint.parents[1] / "resolved_config.json"
    assert '"seed": 77' in resolved.read_text(encoding="utf-8")
    assert not list((tmp_path / "runs").rglob("test"))
