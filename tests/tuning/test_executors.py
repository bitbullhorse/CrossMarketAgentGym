from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

from crossmarket_agentgym.rl.config import load_train_run_config
from crossmarket_agentgym.tuning.config import ExecutorConfig, load_tuning_run_config
from crossmarket_agentgym.tuning.executors import LocalTrialExecutor, RayTrialExecutor
from crossmarket_agentgym.tuning.models import TrialResult, TrialSuggestion
from crossmarket_agentgym.tuning.runner import FunctionalObjective


def _suggestions() -> list[TrialSuggestion]:
    return [
        TrialSuggestion(trial_id=2, parameters={"x": 2.0}),
        TrialSuggestion(trial_id=1, parameters={"x": 1.0}),
    ]


def test_local_executor_preserves_order_and_isolates_failure() -> None:
    def objective(parameters: dict[str, object]) -> float:
        value = float(parameters["x"])
        if value == 1.0:
            raise RuntimeError("fixture failure")
        return -value

    results = LocalTrialExecutor().evaluate(
        _suggestions(),
        FunctionalObjective(objective),
    )
    assert [result.trial_id for result in results] == [2, 1]
    assert [result.status for result in results] == ["completed", "failed"]


def test_executor_config_keeps_local_and_ray_resources_explicit() -> None:
    assert ExecutorConfig().type == "local"
    ray = ExecutorConfig(type="ray", num_cpus_per_trial=2, num_gpus_per_trial=1)
    assert ray.num_gpus_per_trial == 1.0
    with pytest.raises(ValidationError, match="local executor"):
        ExecutorConfig(type="local", num_gpus_per_trial=1)
    with pytest.raises(ValidationError):
        ExecutorConfig(type="ray", num_cpus_per_trial=0)


def test_ray_gpu_example_keeps_search_scheduler_and_executor_separate() -> None:
    config = load_tuning_run_config(Path("configs/tune/ppo_pso_ray_gpu.yaml"))
    assert config.searcher.type == "pso"
    assert config.scheduler.type == "asha"
    assert config.executor.type == "ray"
    assert config.executor.num_gpus_per_trial == 1.0
    assert config.objective.base_train_config is not None
    train = load_train_run_config(config.objective.base_train_config)
    assert train.trainer.device == "cuda"


def test_ray_executor_uses_resources_and_restores_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = ModuleType("ray")
    fake.initialized = False  # type: ignore[attr-defined]
    fake.remote_options = {}  # type: ignore[attr-defined]
    fake.shutdown_called = False  # type: ignore[attr-defined]

    def is_initialized() -> bool:
        return bool(fake.initialized)  # type: ignore[attr-defined]

    def init(**kwargs: object) -> None:
        assert kwargs["address"] == "auto"
        fake.initialized = True  # type: ignore[attr-defined]

    def remote(**options: float):
        fake.remote_options = options  # type: ignore[attr-defined]

        def decorate(function):
            class RemoteFunction:
                @staticmethod
                def remote(*args: object) -> TrialResult:
                    return function(*args)

            return RemoteFunction()

        return decorate

    def get(references: list[TrialResult]) -> list[TrialResult]:
        return references

    def shutdown() -> None:
        fake.shutdown_called = True  # type: ignore[attr-defined]

    fake.is_initialized = is_initialized  # type: ignore[attr-defined]
    fake.init = init  # type: ignore[attr-defined]
    fake.remote = remote  # type: ignore[attr-defined]
    fake.get = get  # type: ignore[attr-defined]
    fake.shutdown = shutdown  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ray", fake)

    executor = RayTrialExecutor(
        address="auto",
        num_cpus_per_trial=2.0,
        num_gpus_per_trial=0.5,
    )
    results = executor.evaluate(
        _suggestions(),
        FunctionalObjective(lambda values: -float(values["x"])),
    )
    assert [result.trial_id for result in results] == [2, 1]
    assert fake.remote_options == {"num_cpus": 2.0, "num_gpus": 0.5}  # type: ignore[attr-defined]
    executor.close()
    assert fake.shutdown_called is True  # type: ignore[attr-defined]
