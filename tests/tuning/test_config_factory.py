from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from crossmarket_agentgym.tuning.config import (
    ObjectiveConfig,
    SchedulerConfig,
    SearcherConfig,
    TuningRunConfig,
    load_tuning_run_config,
)
from crossmarket_agentgym.tuning.factory import create_scheduler, create_searcher
from crossmarket_agentgym.tuning.searchers import SEARCHERS


@pytest.mark.parametrize("name", list(SEARCHERS))
def test_factory_builds_every_configured_searcher(name: str) -> None:
    searcher = create_searcher(SearcherConfig(type=name))
    assert searcher.name == name


@pytest.mark.parametrize("name", ["fifo", "median", "asha", "hyperband", "pbt"])
def test_factory_builds_every_independent_scheduler(name: str) -> None:
    scheduler = create_scheduler(
        SchedulerConfig(type=name),
        searcher_name="pso",
        primary_direction="maximize",
    )
    assert scheduler.name == name


def test_strict_tuning_config_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SearcherConfig.model_validate({"type": "random", "unknown": True})


def test_yaml_loader_accepts_name_keyed_parameters_and_resolves_train_path(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "study.yaml"
    config_path.write_text(
        """
study_name: yaml-study
max_trials: 4
directions: [maximize]
search_space:
  parameters:
    learning_rate:
      kind: float
      low: 0.0001
      high: 0.01
      log: true
    n_steps:
      kind: int
      low: 4
      high: 8
      step: 4
    batch_size:
      kind: int
      low: 2
      high: 8
      step: 2
  constraints:
    - batch_size <= n_steps
searcher:
  type: pso
  population_size: 4
scheduler:
  type: asha
  max_resource: 8
objective:
  type: ppo_validation
  base_train_config: base.yaml
  total_timesteps: 8
""",
        encoding="utf-8",
    )
    config = load_tuning_run_config(config_path)
    assert isinstance(config, TuningRunConfig)
    assert config.search_space.parameters[0].name == "learning_rate"
    assert config.objective.base_train_config == (tmp_path / "base.yaml").resolve()
    config.search_space.validate_candidate(
        {"learning_rate": 0.001, "n_steps": 4, "batch_size": 4}
    )
    with pytest.raises(ValueError, match="violates constraint"):
        config.search_space.validate_candidate(
            {"learning_rate": 0.001, "n_steps": 4, "batch_size": 8}
        )


def test_multi_objective_direction_count_is_validated() -> None:
    with pytest.raises(ValidationError, match="requires 4 directions"):
        TuningRunConfig.model_validate(
            {
                "study_name": "bad-directions",
                "directions": ["maximize"],
                "search_space": {
                    "parameters": [
                        {"name": "x", "kind": "float", "low": 0, "high": 1}
                    ]
                },
                "objective": {"mode": "multi_objective"},
            }
        )


def test_stage_b_requires_five_seeds_and_walk_forward() -> None:
    with pytest.raises(ValidationError, match="at least five seeds"):
        ObjectiveConfig(
            type="ppo_validation",
            base_train_config=Path("base.yaml"),
            seeds=(1, 2, 3),
        )
    with pytest.raises(ValidationError, match="walk-forward"):
        ObjectiveConfig(
            type="ppo_validation",
            base_train_config=Path("base.yaml"),
            seeds=(1, 2, 3, 4, 5),
            walk_forward_folds=1,
        )
