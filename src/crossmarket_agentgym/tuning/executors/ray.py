"""Optional Ray adapter for parallel objective evaluation only."""

from __future__ import annotations

from typing import Any

from crossmarket_agentgym.tuning.executors.base import (
    ObjectiveEvaluator,
    evaluate_safely,
)
from crossmarket_agentgym.tuning.models import TrialResult, TrialSuggestion


class RayTrialExecutor:
    """Allocate CPU/GPU resources while preserving local scheduling authority."""

    name = "ray"

    def __init__(
        self,
        *,
        address: str | None = None,
        num_cpus_per_trial: float = 1.0,
        num_gpus_per_trial: float = 0.0,
        shutdown_on_close: bool = True,
    ) -> None:
        if num_cpus_per_trial <= 0.0:
            raise ValueError("num_cpus_per_trial must be positive")
        if num_gpus_per_trial < 0.0:
            raise ValueError("num_gpus_per_trial cannot be negative")
        self.address = address
        self.num_cpus_per_trial = num_cpus_per_trial
        self.num_gpus_per_trial = num_gpus_per_trial
        self.shutdown_on_close = shutdown_on_close
        self._owns_runtime = False
        self._ray: Any | None = None

    def _runtime(self) -> Any:
        if self._ray is not None:
            return self._ray
        try:
            import ray
        except ImportError as error:
            raise RuntimeError(
                "Ray execution requires: pip install 'crossmarket-agent-gym[ray]'"
            ) from error
        if not ray.is_initialized():
            ray.init(address=self.address, ignore_reinit_error=False)
            self._owns_runtime = True
        self._ray = ray
        return ray

    def evaluate(
        self,
        suggestions: list[TrialSuggestion],
        evaluator: ObjectiveEvaluator,
    ) -> list[TrialResult]:
        """Dispatch independent trials and restore deterministic suggestion order."""
        if not suggestions:
            return []
        ray = self._runtime()
        remote_evaluate = ray.remote(
            num_cpus=self.num_cpus_per_trial,
            num_gpus=self.num_gpus_per_trial,
        )(evaluate_safely)
        references = [
            remote_evaluate.remote(evaluator, suggestion)
            for suggestion in suggestions
        ]
        raw = ray.get(references)
        return [TrialResult.model_validate(item) for item in raw]

    def close(self) -> None:
        """Shut down only a Ray runtime created by this adapter."""
        if (
            self._ray is not None
            and self._owns_runtime
            and self.shutdown_on_close
        ):
            self._ray.shutdown()
        self._ray = None
        self._owns_runtime = False
