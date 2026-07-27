"""Formal strategy, generalization, mechanism, Agent, and HPO runners."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from crossmarket_agentgym.experiments.agent_runs import (
    _layers,
    _load_prompt_bundle,
    run_group_e,
)
from crossmarket_agentgym.experiments.generalization_runs import (
    run_group_c,
)
from crossmarket_agentgym.experiments.hpo_runs import (
    _default_parameters,
    _folds,
    _objective,
    _run_search,
    _space,
    run_group_f,
)
from crossmarket_agentgym.experiments.mechanism_runs import run_group_d
from crossmarket_agentgym.experiments.strategy_runs import (
    formal_train_config,
    run_group_b,
)
from crossmarket_agentgym.experiments.training import (
    build_formal_partitioned_environments,
)
from crossmarket_agentgym.tuning.models import (
    StudyState,
    TrialResult,
)


def test_formal_config_and_baseline_group_b(
    formal_sample: tuple[Path, object],
    tmp_path: Path,
) -> None:
    workspace, protocol = formal_sample
    config = formal_train_config(
        protocol,
        workspace_root=workspace,
        run_name="test",
        output_dir=tmp_path,
        algorithm="PPO",
        seed=1024,
        total_timesteps=1,
    )
    assert config.split.train_end_execution_index == 1
    assert config.split.validation_end_execution_index == 2
    assert config.split.test_end_execution_index == 4
    assert config.observation.market_window_layout == "flat"
    environments = build_formal_partitioned_environments(protocol, config)
    _, info = environments["train"].reset()
    _, _, _, _, step_info = environments["train"].step(
        environments["train"].action_space.sample()
    )
    assert info["observation_date"] < protocol.partitions.train.start.isoformat()
    assert step_info["execution_date"] == protocol.partitions.train.start.isoformat()
    result = run_group_b(
        protocol=protocol,
        workspace_root=workspace,
        method="cash",
        seed=1024,
        run_dir=tmp_path / "cash",
    )
    assert result["trained"] is False
    assert result["test_evaluation_count"] == 1
    assert result["test_metrics"]["mean_return"] == pytest.approx(0.0)
    with pytest.raises(ValueError, match="unsupported"):
        run_group_b(
            protocol=protocol,
            workspace_root=workspace,
            method="unknown",
            seed=1024,
            run_dir=tmp_path / "unknown",
        )


def test_formal_agent_prompt_bundle_is_hash_bound(
    formal_sample: tuple[Path, object],
) -> None:
    workspace, protocol = formal_sample
    prompts = _load_prompt_bundle(protocol, workspace)
    assert set(prompts) == {
        "research_coordinator",
        "risk_manager",
        "market_regime",
    }
    assert "cannot" in prompts["risk_manager"].lower()


def test_joint_generalization_runs_with_hidden_inactive_features(
    formal_sample: tuple[Path, object],
    tmp_path: Path,
) -> None:
    workspace, protocol = formal_sample
    result = run_group_c(
        protocol=protocol,
        workspace_root=workspace,
        method="joint_market",
        seed=1024,
        run_dir=tmp_path / "joint",
    )
    assert result["target_features_visible_during_training"] is False
    assert result["subruns"]["joint"]["test_evaluation_count"] == 1
    with pytest.raises(ValueError, match="unsupported"):
        run_group_c(
            protocol=protocol,
            workspace_root=workspace,
            method="unknown",
            seed=1024,
            run_dir=tmp_path / "bad",
        )


@pytest.mark.parametrize(
    "method",
    [
        "no_transaction_cost",
        "no_slippage",
        "no_t_plus_one",
        "no_price_limits",
        "no_suspension",
        "no_fx_variation",
        "synchronous_calendar",
        "no_turnover_cap",
        "minimum_deterministic_risk_projection",
    ],
)
def test_all_mechanism_ablation_branches(
    method: str,
    formal_sample: tuple[Path, object],
    tmp_path: Path,
) -> None:
    workspace, protocol = formal_sample
    result = run_group_d(
        protocol=protocol,
        workspace_root=workspace,
        method=method,
        seed=1024,
        run_dir=tmp_path / method,
    )
    assert result["test_evaluation_count_per_arm"] == 1
    assert result["deterministic_risk_layer_bypassed"] is False
    assert "sharpe" in result["variant_metrics"]


def test_agent_preset_geometry_and_no_llm_run(
    formal_sample: tuple[Path, object],
    tmp_path: Path,
) -> None:
    workspace, protocol = formal_sample
    for method in protocol.agents.presets:
        preset, layers = _layers(method, protocol)
        assert preset
        if method == "no_llm":
            assert not any(
                (
                    layers.research.enabled,
                    layers.risk.enabled,
                    layers.hierarchical.enabled,
                )
            )
    result = run_group_e(
        protocol=protocol,
        workspace_root=workspace,
        method="no_llm",
        seed=1024,
        run_dir=workspace / "results" / "no_llm",
    )
    assert result["provider_network_used"] is False
    assert result["replay_consistency"] is True
    assert result["deterministic_risk_layer_bypassed"] is False
    assert result["test_evaluation_count"] == 1


class _FastObjective:
    def evaluate(self, suggestion: Any) -> TrialResult:
        return TrialResult(
            trial_id=suggestion.trial_id,
            parameters=suggestion.parameters,
            status="completed",
            objectives=(float(suggestion.trial_id),),
            metrics={
                "validation_median_sharpe": float(suggestion.trial_id),
                "validation_sharpe_instability": 0.0,
            },
            resource=6.0,
        )


def test_hpo_helpers_and_test_lock(
    formal_sample: tuple[Path, object],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, protocol = formal_sample
    assert _space(protocol).dimension == 4
    assert len(_folds(protocol, workspace_root=workspace, seed=1024)) == 3
    objective, base = _objective(
        protocol,
        workspace_root=workspace,
        seed=1024,
        output_dir=tmp_path / "objective",
        multi_objective=False,
    )
    assert objective.fold_splits is not None
    assert base.trainer.total_timesteps == protocol.hpo.timesteps_per_trial

    default_state, schedulers = _run_search(
        protocol=protocol,
        method="default",
        seed=1024,
        run_dir=tmp_path / "default",
        objective=_FastObjective(),  # type: ignore[arg-type]
    )
    assert len(default_state.results) == protocol.hpo.trials_per_searcher
    assert schedulers == ()
    random_state, schedulers = _run_search(
        protocol=protocol,
        method="random",
        seed=1024,
        run_dir=tmp_path / "random",
        objective=_FastObjective(),  # type: ignore[arg-type]
    )
    assert len(random_state.results) == protocol.hpo.trials_per_searcher
    assert schedulers == ("asha",)

    state = StudyState(
        study_name="fake",
        directions=("maximize",),
        results=(
            TrialResult(
                trial_id=0,
                parameters=_default_parameters(),
                status="completed",
                objectives=(1.0,),
                metrics={
                    "validation_median_sharpe": 1.0,
                    "validation_sharpe_instability": 0.1,
                },
                resource=6.0,
            ),
        ),
    )
    monkeypatch.setattr(
        "crossmarket_agentgym.experiments.hpo_runs._objective",
        lambda *args, **kwargs: (_FastObjective(), object()),
    )
    monkeypatch.setattr(
        "crossmarket_agentgym.experiments.hpo_runs._run_search",
        lambda **kwargs: (state, ("asha",)),
    )
    monkeypatch.setattr(
        "crossmarket_agentgym.experiments.hpo_runs._locked_test",
        lambda **kwargs: (
            {"sharpe": 0.8, "mean_return": 0.1},
            {
                "trained_timesteps": 8,
                "independent_retrain_seed": 1_001_024,
                "test_evaluation_count": 1,
            },
        ),
    )
    monkeypatch.setattr(
        "crossmarket_agentgym.experiments.hpo_runs.write_study_report",
        lambda state, path: (path / "study.json", path / "study.md"),
    )
    result = run_group_f(
        protocol=protocol,
        workspace_root=workspace,
        method="random",
        seed=1024,
        run_dir=tmp_path / "formal_f",
    )
    assert result["test_partition_visible_during_search"] is False
    assert result["locked_test_score"] == pytest.approx(0.8)
    assert result["tuning_overfit_gap"] == pytest.approx(0.2)
