from __future__ import annotations

from pathlib import Path

import pytest

from crossmarket_agentgym.rl import CallbackConfig, load_train_run_config
from crossmarket_agentgym.tuning import ParameterSpec, SearchSpace, SQLiteStudyStore, TrialRunner
from crossmarket_agentgym.tuning.config import ObjectiveConfig, SearcherConfig
from crossmarket_agentgym.tuning.factory import create_searcher
from crossmarket_agentgym.tuning.rl_objective import PPOValidationObjective
from crossmarket_agentgym.tuning.schedulers import FIFOScheduler
from crossmarket_agentgym.tuning.searchers import SEARCHERS


@pytest.mark.parametrize("searcher_name", list(SEARCHERS))
def test_every_searcher_runs_a_small_partition_safe_ppo_trial(
    searcher_name: str,
    tmp_path: Path,
) -> None:
    """Exercise each searcher through the real Trainer/validation objective boundary."""
    base = load_train_run_config(Path("configs/train/ppo_tune_smoke.yaml"))
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
            base_train_config=Path("configs/train/ppo_tune_smoke.yaml"),
            budget_stage="stage_a",
            seeds=(19,),
            walk_forward_folds=1,
            total_timesteps=4,
        ),
        output_dir=tmp_path / "trials",
    )
    space = SearchSpace(
        parameters=(
            ParameterSpec(
                name="learning_rate",
                kind="float",
                low=1.0e-4,
                high=1.0e-3,
                log=True,
            ),
        )
    )
    searcher = create_searcher(
        SearcherConfig(type=searcher_name, seed=23, population_size=4)
    )
    with SQLiteStudyStore(tmp_path / "study.sqlite3") as store:
        state = TrialRunner(
            study_name=f"ppo-{searcher_name}",
            directions=("maximize",),
            search_space=space,
            searcher=searcher,
            scheduler=FIFOScheduler(),
            evaluator=objective,
            store=store,
        ).run(1)

    assert len(state.results) == 1
    assert state.results[0].status == "completed"
    assert state.results[0].metrics["validation_fold_count"] == 1
    assert not list(tmp_path.rglob("*test*"))
