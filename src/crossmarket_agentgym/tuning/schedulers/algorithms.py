"""FIFO, median stopping, ASHA, HyperBand, and PBT resource schedulers."""

from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np

from crossmarket_agentgym.tuning.schedulers.base import TrialDecision

MetricDirection = Literal["maximize", "minimize"]


def _utility(metric: float, direction: MetricDirection) -> float:
    if not math.isfinite(metric):
        return -math.inf
    return metric if direction == "maximize" else -metric


class FIFOScheduler:
    """Run trials in submission order without early stopping."""

    name = "fifo"

    def __init__(self) -> None:
        self.active: list[int] = []
        self.completed: list[int] = []

    def on_trial_add(self, trial_id: int) -> None:
        if trial_id not in self.active and trial_id not in self.completed:
            self.active.append(trial_id)

    def on_result(
        self,
        trial_id: int,
        resource: float,
        metric: float,
        parameters: dict[str, Any] | None = None,
    ) -> TrialDecision:
        del resource, metric, parameters
        self.on_trial_add(trial_id)
        return TrialDecision(action="continue", reason="fifo")

    def on_complete(self, trial_id: int, metric: float | None = None) -> None:
        del metric
        if trial_id in self.active:
            self.active.remove(trial_id)
        if trial_id not in self.completed:
            self.completed.append(trial_id)

    def state_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "active": self.active,
            "completed": self.completed,
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        if state.get("name") != self.name:
            raise ValueError("scheduler state belongs to a different scheduler")
        self.active = [int(value) for value in state["active"]]
        self.completed = [int(value) for value in state["completed"]]


class MedianStoppingScheduler(FIFOScheduler):
    """Stop trials below the historical median at comparable resource."""

    name = "median"

    def __init__(
        self,
        *,
        grace_period: float = 1.0,
        min_trials: int = 3,
        direction: MetricDirection = "maximize",
    ) -> None:
        super().__init__()
        self.grace_period = grace_period
        self.min_trials = min_trials
        self.direction = direction
        self.history: dict[str, list[float]] = {}

    def on_result(
        self,
        trial_id: int,
        resource: float,
        metric: float,
        parameters: dict[str, Any] | None = None,
    ) -> TrialDecision:
        del parameters
        self.on_trial_add(trial_id)
        key = f"{resource:.12g}"
        prior = self.history.setdefault(key, [])
        stop = (
            resource >= self.grace_period
            and len(prior) >= self.min_trials
            and _utility(metric, self.direction)
            < float(np.median([_utility(value, self.direction) for value in prior]))
        )
        prior.append(metric)
        return TrialDecision(
            action="stop" if stop else "continue",
            reason="below_median" if stop else "median_continue",
        )

    def state_dict(self) -> dict[str, Any]:
        return {
            **super().state_dict(),
            "grace_period": self.grace_period,
            "min_trials": self.min_trials,
            "direction": self.direction,
            "history": self.history,
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        super().load_state_dict(state)
        self.history = {
            str(key): [float(value) for value in values]
            for key, values in state["history"].items()
        }


class ASHAScheduler(FIFOScheduler):
    """Asynchronous successive halving over independent resource rungs."""

    name = "asha"

    def __init__(
        self,
        *,
        grace_period: float = 1.0,
        max_resource: float = 81.0,
        reduction_factor: int = 3,
        direction: MetricDirection = "maximize",
    ) -> None:
        super().__init__()
        if grace_period <= 0 or max_resource < grace_period or reduction_factor < 2:
            raise ValueError("invalid ASHA resource geometry")
        self.grace_period = grace_period
        self.max_resource = max_resource
        self.reduction_factor = reduction_factor
        self.direction = direction
        levels: list[float] = []
        level = grace_period
        while level <= max_resource + 1e-12:
            levels.append(level)
            level *= reduction_factor
        self.rungs: dict[str, dict[int, float]] = {
            f"{value:.12g}": {} for value in levels
        }
        self.reached: dict[int, set[str]] = {}

    def on_result(
        self,
        trial_id: int,
        resource: float,
        metric: float,
        parameters: dict[str, Any] | None = None,
    ) -> TrialDecision:
        del parameters
        self.on_trial_add(trial_id)
        reached = self.reached.setdefault(trial_id, set())
        eligible = [
            key
            for key in self.rungs
            if float(key) <= resource + 1e-12 and key not in reached
        ]
        for key in sorted(eligible, key=float):
            rung = self.rungs[key]
            rung[trial_id] = metric
            reached.add(key)
            if len(rung) >= self.reduction_factor:
                ordered = sorted(
                    rung,
                    key=lambda item: _utility(rung[item], self.direction),
                    reverse=True,
                )
                keep = max(1, math.ceil(len(ordered) / self.reduction_factor))
                if trial_id not in ordered[:keep]:
                    return TrialDecision(
                        action="stop",
                        reason=f"asha_rung_{key}",
                    )
        if resource >= self.max_resource:
            return TrialDecision(action="stop", reason="max_resource_reached")
        return TrialDecision(action="continue", reason="asha_continue")

    def state_dict(self) -> dict[str, Any]:
        return {
            **super().state_dict(),
            "grace_period": self.grace_period,
            "max_resource": self.max_resource,
            "reduction_factor": self.reduction_factor,
            "direction": self.direction,
            "rungs": self.rungs,
            "reached": {
                trial_id: sorted(levels)
                for trial_id, levels in self.reached.items()
            },
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        super().load_state_dict(state)
        self.rungs = {
            str(level): {
                int(trial_id): float(metric)
                for trial_id, metric in values.items()
            }
            for level, values in state["rungs"].items()
        }
        self.reached = {
            int(trial_id): {str(level) for level in levels}
            for trial_id, levels in state["reached"].items()
        }


class HyperBandScheduler(FIFOScheduler):
    """Multiple ASHA brackets with deterministic trial assignment."""

    name = "hyperband"

    def __init__(
        self,
        *,
        min_resource: float = 1.0,
        max_resource: float = 81.0,
        reduction_factor: int = 3,
        direction: MetricDirection = "maximize",
    ) -> None:
        super().__init__()
        if min_resource <= 0 or max_resource < min_resource:
            raise ValueError("invalid HyperBand resource geometry")
        bracket_count = int(
            math.floor(math.log(max_resource / min_resource, reduction_factor))
        ) + 1
        self.brackets = [
            ASHAScheduler(
                grace_period=min_resource * reduction_factor**index,
                max_resource=max_resource,
                reduction_factor=reduction_factor,
                direction=direction,
            )
            for index in range(bracket_count)
        ]
        self.assignments: dict[int, int] = {}

    def on_trial_add(self, trial_id: int) -> None:
        super().on_trial_add(trial_id)
        bracket = trial_id % len(self.brackets)
        self.assignments.setdefault(trial_id, bracket)
        self.brackets[bracket].on_trial_add(trial_id)

    def on_result(
        self,
        trial_id: int,
        resource: float,
        metric: float,
        parameters: dict[str, Any] | None = None,
    ) -> TrialDecision:
        self.on_trial_add(trial_id)
        bracket = self.assignments[trial_id]
        decision = self.brackets[bracket].on_result(
            trial_id,
            resource,
            metric,
            parameters,
        )
        return decision.model_copy(
            update={"reason": f"hyperband_b{bracket}:{decision.reason}"}
        )

    def on_complete(self, trial_id: int, metric: float | None = None) -> None:
        super().on_complete(trial_id, metric)
        if trial_id in self.assignments:
            self.brackets[self.assignments[trial_id]].on_complete(trial_id, metric)

    def state_dict(self) -> dict[str, Any]:
        return {
            **super().state_dict(),
            "assignments": self.assignments,
            "brackets": [bracket.state_dict() for bracket in self.brackets],
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        super().load_state_dict(state)
        self.assignments = {
            int(trial_id): int(bracket)
            for trial_id, bracket in state["assignments"].items()
        }
        if len(state["brackets"]) != len(self.brackets):
            raise ValueError("HyperBand bracket geometry changed")
        for bracket, bracket_state in zip(
            self.brackets, state["brackets"], strict=True
        ):
            bracket.load_state_dict(bracket_state)


class PopulationBasedTrainingScheduler(FIFOScheduler):
    """Exploit top trials and perturb their parameters at fixed intervals."""

    name = "pbt"

    def __init__(
        self,
        *,
        perturbation_interval: float = 10.0,
        quantile_fraction: float = 0.25,
        direction: MetricDirection = "maximize",
        perturbation_factors: tuple[float, float] = (0.8, 1.2),
    ) -> None:
        super().__init__()
        if perturbation_interval <= 0 or not 0 < quantile_fraction <= 0.5:
            raise ValueError("invalid PBT schedule")
        self.perturbation_interval = perturbation_interval
        self.quantile_fraction = quantile_fraction
        self.direction = direction
        self.perturbation_factors = perturbation_factors
        self.latest: dict[int, tuple[float, float, dict[str, Any]]] = {}
        self.last_exploit_resource: dict[int, float] = {}

    def on_result(
        self,
        trial_id: int,
        resource: float,
        metric: float,
        parameters: dict[str, Any] | None = None,
    ) -> TrialDecision:
        self.on_trial_add(trial_id)
        self.latest[trial_id] = (resource, metric, dict(parameters or {}))
        previous = self.last_exploit_resource.get(trial_id, 0.0)
        if resource - previous < self.perturbation_interval or len(self.latest) < 4:
            return TrialDecision(action="continue", reason="pbt_wait")
        ordered = sorted(
            self.latest,
            key=lambda item: _utility(self.latest[item][1], self.direction),
            reverse=True,
        )
        count = max(1, int(math.ceil(len(ordered) * self.quantile_fraction)))
        bottom = set(ordered[-count:])
        if trial_id not in bottom:
            return TrialDecision(action="continue", reason="pbt_top_or_middle")
        source = ordered[0]
        source_parameters = self.latest[source][2]
        patch = {
            key: (
                value
                * self.perturbation_factors[
                    (trial_id + index) % len(self.perturbation_factors)
                ]
                if isinstance(value, int | float) and not isinstance(value, bool)
                else value
            )
            for index, (key, value) in enumerate(sorted(source_parameters.items()))
        }
        self.last_exploit_resource[trial_id] = resource
        return TrialDecision(
            action="exploit",
            reason="pbt_bottom_quantile",
            source_trial_id=source,
            parameter_patch=patch,
        )

    def state_dict(self) -> dict[str, Any]:
        return {
            **super().state_dict(),
            "latest": {
                trial_id: {
                    "resource": values[0],
                    "metric": values[1],
                    "parameters": values[2],
                }
                for trial_id, values in self.latest.items()
            },
            "last_exploit_resource": self.last_exploit_resource,
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        super().load_state_dict(state)
        self.latest = {
            int(trial_id): (
                float(values["resource"]),
                float(values["metric"]),
                dict(values["parameters"]),
            )
            for trial_id, values in state["latest"].items()
        }
        self.last_exploit_resource = {
            int(trial_id): float(resource)
            for trial_id, resource in state["last_exploit_resource"].items()
        }
