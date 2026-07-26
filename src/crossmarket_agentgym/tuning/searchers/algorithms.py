"""Nine deterministic core hyperparameter search algorithms."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from crossmarket_agentgym.tuning.models import (
    StudyState,
    TrialResult,
    TrialSuggestion,
    dominates,
    scalar_utility,
)
from crossmarket_agentgym.tuning.searchers.base import BaseSearcher

Vector = NDArray[np.float64]


def _vector(result: TrialResult, searcher: BaseSearcher) -> Vector:
    return searcher._require_space().encode(result.parameters)


def _nondominated_fronts(
    results: list[TrialResult],
    directions: tuple[str, ...],
) -> list[list[TrialResult]]:
    remaining = [result for result in results if result.status == "completed"]
    fronts: list[list[TrialResult]] = []
    while remaining:
        front = [
            candidate
            for candidate in remaining
            if not any(
                dominates(other, candidate, directions)  # type: ignore[arg-type]
                for other in remaining
                if other.trial_id != candidate.trial_id
            )
        ]
        fronts.append(front)
        front_ids = {result.trial_id for result in front}
        remaining = [result for result in remaining if result.trial_id not in front_ids]
    return fronts


def _crowding(
    front: list[TrialResult],
    objective_count: int,
) -> dict[int, float]:
    distance = {result.trial_id: 0.0 for result in front}
    if len(front) <= 2:
        return {result.trial_id: math.inf for result in front}
    for objective in range(objective_count):
        ordered = sorted(front, key=lambda result: result.objectives[objective])
        distance[ordered[0].trial_id] = math.inf
        distance[ordered[-1].trial_id] = math.inf
        low = ordered[0].objectives[objective]
        high = ordered[-1].objectives[objective]
        if high <= low:
            continue
        for index in range(1, len(ordered) - 1):
            distance[ordered[index].trial_id] += (
                ordered[index + 1].objectives[objective]
                - ordered[index - 1].objectives[objective]
            ) / (high - low)
    return distance


class RandomSearch(BaseSearcher):
    """Independent uniform samples in the mixed search space."""

    name = "random"

    def suggest(self, n: int = 1) -> list[TrialSuggestion]:
        space = self._require_space()
        return [
            self._suggestion(space.encode(space.sample(self.rng)))
            for _ in range(n)
        ]


class GridSearch(BaseSearcher):
    """Finite deterministic Cartesian grid."""

    name = "grid"

    def __init__(self, seed: int = 1024) -> None:
        super().__init__(seed)
        self._grid: list[dict[str, Any]] = []
        self._index = 0

    def initialize(self, search_space: Any, study_state: StudyState) -> None:
        super().initialize(search_space, study_state)
        self._grid = self._require_space().grid()
        self._index = len(study_state.results)

    def suggest(self, n: int = 1) -> list[TrialSuggestion]:
        suggestions: list[TrialSuggestion] = []
        for candidate in self._grid[self._index : self._index + n]:
            suggestions.append(
                self._suggestion(self._require_space().encode(candidate))
            )
        self._index += len(suggestions)
        return suggestions

    def state_dict(self) -> dict[str, Any]:
        return {**self._base_state(), "index": self._index}

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self._load_base_state(state)
        self._index = int(state["index"])


class TPESearch(BaseSearcher):
    """Tree-structured Parzen estimator over normalized mixed coordinates."""

    name = "tpe"

    def __init__(
        self,
        seed: int = 1024,
        *,
        startup_trials: int = 8,
        candidate_count: int = 32,
        gamma: float = 0.25,
    ) -> None:
        super().__init__(seed)
        self.startup_trials = startup_trials
        self.candidate_count = candidate_count
        self.gamma = gamma

    @staticmethod
    def _log_density(samples: NDArray[np.float64], values: Vector) -> float:
        bandwidth = np.maximum(samples.std(axis=0, ddof=0), 0.08)
        z = (values - samples) / bandwidth
        component = np.exp(-0.5 * z * z) / bandwidth
        density = np.maximum(component.mean(axis=0), 1e-300)
        return float(np.log(density).sum())

    def suggest(self, n: int = 1) -> list[TrialSuggestion]:
        completed = [result for result in self.results if result.status == "completed"]
        suggestions: list[TrialSuggestion] = []
        for _ in range(n):
            if len(completed) < self.startup_trials:
                vector = self.rng.random(self._require_space().dimension)
            else:
                ordered = sorted(
                    completed,
                    key=lambda result: scalar_utility(result, self.directions),
                    reverse=True,
                )
                split = max(2, int(math.ceil(len(ordered) * self.gamma)))
                good = np.vstack([_vector(result, self) for result in ordered[:split]])
                bad_items = ordered[split:] or ordered[-2:]
                bad = np.vstack([_vector(result, self) for result in bad_items])
                candidates = np.clip(
                    self.rng.normal(
                        good.mean(axis=0),
                        np.maximum(good.std(axis=0), 0.1),
                        size=(self.candidate_count, good.shape[1]),
                    ),
                    0.0,
                    1.0,
                )
                scores = [
                    self._log_density(good, candidate)
                    - self._log_density(bad, candidate)
                    for candidate in candidates
                ]
                vector = candidates[int(np.argmax(scores))]
            suggestions.append(self._suggestion(vector))
        return suggestions


class CMAESSearch(BaseSearcher):
    """Compact covariance-matrix adaptation evolution strategy."""

    name = "cma_es"

    def __init__(
        self,
        seed: int = 1024,
        *,
        population_size: int = 8,
        sigma: float = 0.25,
    ) -> None:
        super().__init__(seed)
        self.population_size = population_size
        self.sigma = sigma
        self.mean: Vector | None = None
        self.covariance: NDArray[np.float64] | None = None

    def initialize(self, search_space: Any, study_state: StudyState) -> None:
        super().initialize(search_space, study_state)
        dimension = self._require_space().dimension
        self.mean = np.full(dimension, 0.5)
        self.covariance = np.eye(dimension)

    def suggest(self, n: int = 1) -> list[TrialSuggestion]:
        if self.mean is None or self.covariance is None:
            raise RuntimeError("CMA-ES is not initialized")
        return [
            self._suggestion(
                self.rng.multivariate_normal(
                    self.mean,
                    self.covariance * self.sigma**2,
                )
            )
            for _ in range(n)
        ]

    def observe(self, results: list[TrialResult]) -> None:
        super().observe(results)
        completed = [result for result in results if result.status == "completed"]
        if not completed:
            self.sigma = max(0.02, self.sigma * 0.9)
            return
        ordered = sorted(
            completed,
            key=lambda result: scalar_utility(result, self.directions),
            reverse=True,
        )
        elite = ordered[: max(1, len(ordered) // 2)]
        matrix = np.vstack([_vector(result, self) for result in elite])
        new_mean = matrix.mean(axis=0)
        centered = matrix - new_mean
        covariance = centered.T @ centered / max(1, len(matrix))
        covariance += np.eye(matrix.shape[1]) * 1e-4
        self.mean = 0.3 * self.mean + 0.7 * new_mean if self.mean is not None else new_mean
        self.covariance = covariance
        self.sigma = max(0.02, self.sigma * 0.98)
        self.generation += 1

    def state_dict(self) -> dict[str, Any]:
        return {
            **self._base_state(),
            "mean": None if self.mean is None else self.mean.tolist(),
            "covariance": (
                None if self.covariance is None else self.covariance.tolist()
            ),
            "sigma": self.sigma,
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self._load_base_state(state)
        self.mean = np.asarray(state["mean"], dtype=np.float64)
        self.covariance = np.asarray(state["covariance"], dtype=np.float64)
        self.sigma = float(state["sigma"])


class NSGAIISearch(BaseSearcher):
    """Multi-objective nondominated sorting genetic algorithm."""

    name = "nsga_ii"

    def __init__(
        self,
        seed: int = 1024,
        *,
        population_size: int = 12,
        mutation_rate: float = 0.15,
    ) -> None:
        super().__init__(seed)
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.population: list[TrialResult] = []

    def _select_parent(self) -> TrialResult:
        fronts = _nondominated_fronts(self.population, self.directions)
        ranks = {
            result.trial_id: rank
            for rank, front in enumerate(fronts)
            for result in front
        }
        indices = self.rng.integers(0, len(self.population), size=2)
        first = self.population[int(indices[0])]
        second = self.population[int(indices[1])]
        return first if ranks[first.trial_id] <= ranks[second.trial_id] else second

    def suggest(self, n: int = 1) -> list[TrialSuggestion]:
        suggestions: list[TrialSuggestion] = []
        dimension = self._require_space().dimension
        for _ in range(n):
            if len(self.population) < 2:
                child = self.rng.random(dimension)
            else:
                first = _vector(self._select_parent(), self)
                second = _vector(self._select_parent(), self)
                blend = self.rng.random(dimension)
                child = blend * first + (1.0 - blend) * second
                mutation = self.rng.random(dimension) < self.mutation_rate
                child[mutation] += self.rng.normal(0.0, 0.12, mutation.sum())
            suggestions.append(self._suggestion(child))
        return suggestions

    def observe(self, results: list[TrialResult]) -> None:
        super().observe(results)
        combined = self.population + [
            result for result in results if result.status == "completed"
        ]
        selected: list[TrialResult] = []
        for front in _nondominated_fronts(combined, self.directions):
            if len(selected) + len(front) <= self.population_size:
                selected.extend(front)
            else:
                crowding = _crowding(front, len(self.directions))
                selected.extend(
                    sorted(
                        front,
                        key=lambda result: crowding[result.trial_id],
                        reverse=True,
                    )[: self.population_size - len(selected)]
                )
                break
        self.population = selected
        self.generation += 1

    def pareto_front(self) -> list[TrialResult]:
        """Return the current first nondominated front."""
        fronts = _nondominated_fronts(self.population, self.directions)
        return fronts[0] if fronts else []

    def state_dict(self) -> dict[str, Any]:
        return {
            **self._base_state(),
            "population": [result.model_dump(mode="json") for result in self.population],
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self._load_base_state(state)
        self.population = [
            TrialResult.model_validate(item) for item in state["population"]
        ]


class ParticleSwarmSearch(BaseSearcher):
    """Particle swarm optimization with personal and global memories."""

    name = "pso"

    def __init__(
        self,
        seed: int = 1024,
        *,
        population_size: int = 8,
        inertia: float = 0.72,
        cognitive: float = 1.49,
        social: float = 1.49,
    ) -> None:
        super().__init__(seed)
        self.population_size = population_size
        self.inertia = inertia
        self.cognitive = cognitive
        self.social = social
        self.positions: NDArray[np.float64] | None = None
        self.velocities: NDArray[np.float64] | None = None
        self.personal_best: NDArray[np.float64] | None = None
        self.personal_scores: Vector | None = None
        self.global_best: Vector | None = None
        self._issued: set[int] = set()
        self._pending: dict[int, int] = {}
        self._generation_scores: dict[int, float] = {}

    def initialize(self, search_space: Any, study_state: StudyState) -> None:
        super().initialize(search_space, study_state)
        dimension = self._require_space().dimension
        self.positions = self.rng.random((self.population_size, dimension))
        self.velocities = self.rng.uniform(
            -0.1, 0.1, size=(self.population_size, dimension)
        )
        self.personal_best = self.positions.copy()
        self.personal_scores = np.full(self.population_size, -math.inf)
        self.global_best = self.positions[0].copy()

    def suggest(self, n: int = 1) -> list[TrialSuggestion]:
        if self.positions is None:
            raise RuntimeError("PSO is not initialized")
        available = [
            index for index in range(self.population_size) if index not in self._issued
        ][:n]
        suggestions = [
            self._suggestion(
                self.positions[index],
                metadata={"particle": index},
            )
            for index in available
        ]
        for suggestion, index in zip(suggestions, available, strict=True):
            self._issued.add(index)
            self._pending[suggestion.trial_id] = index
        return suggestions

    def observe(self, results: list[TrialResult]) -> None:
        super().observe(results)
        assert self.positions is not None
        assert self.velocities is not None
        assert self.personal_best is not None
        assert self.personal_scores is not None
        assert self.global_best is not None
        for result in results:
            particle = self._pending.pop(result.trial_id)
            score = scalar_utility(result, self.directions)
            self._generation_scores[particle] = score
            if score > self.personal_scores[particle]:
                self.personal_scores[particle] = score
                self.personal_best[particle] = self.positions[particle]
        if len(self._generation_scores) == self.population_size:
            best_index = int(np.argmax(self.personal_scores))
            self.global_best = self.personal_best[best_index].copy()
            random_personal = self.rng.random(self.positions.shape)
            random_global = self.rng.random(self.positions.shape)
            self.velocities = (
                self.inertia * self.velocities
                + self.cognitive
                * random_personal
                * (self.personal_best - self.positions)
                + self.social
                * random_global
                * (self.global_best - self.positions)
            )
            self.positions = np.clip(self.positions + self.velocities, 0.0, 1.0)
            self._issued.clear()
            self._generation_scores.clear()
            self.generation += 1

    def state_dict(self) -> dict[str, Any]:
        def items(value: NDArray[np.float64] | None) -> Any:
            return None if value is None else value.tolist()

        personal_scores = (
            None
            if self.personal_scores is None
            else [
                None if not math.isfinite(score) else float(score)
                for score in self.personal_scores
            ]
        )
        return {
            **self._base_state(),
            "positions": items(self.positions),
            "velocities": items(self.velocities),
            "personal_best": items(self.personal_best),
            "personal_scores": personal_scores,
            "global_best": items(self.global_best),
            "issued": sorted(self._issued),
            "pending": self._pending,
            "generation_scores": {
                index: None if not math.isfinite(score) else score
                for index, score in self._generation_scores.items()
            },
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self._load_base_state(state)
        self.positions = np.asarray(state["positions"], dtype=np.float64)
        self.velocities = np.asarray(state["velocities"], dtype=np.float64)
        self.personal_best = np.asarray(state["personal_best"], dtype=np.float64)
        self.personal_scores = np.asarray(
            [
                -math.inf if value is None else float(value)
                for value in state["personal_scores"]
            ],
            dtype=np.float64,
        )
        self.global_best = np.asarray(state["global_best"], dtype=np.float64)
        self._issued = {int(item) for item in state["issued"]}
        self._pending = {int(key): int(value) for key, value in state["pending"].items()}
        self._generation_scores = {
            int(key): -math.inf if value is None else float(value)
            for key, value in state["generation_scores"].items()
        }


class GeneticAlgorithmSearch(BaseSearcher):
    """Elitist real-coded genetic algorithm."""

    name = "genetic"

    def __init__(
        self,
        seed: int = 1024,
        *,
        population_size: int = 10,
        mutation_rate: float = 0.15,
    ) -> None:
        super().__init__(seed)
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.population: list[tuple[Vector, float]] = []

    def suggest(self, n: int = 1) -> list[TrialSuggestion]:
        dimension = self._require_space().dimension
        suggestions: list[TrialSuggestion] = []
        for _ in range(n):
            if len(self.population) < 2:
                child = self.rng.random(dimension)
            else:
                parents = self.rng.choice(len(self.population), size=2, replace=True)
                first, second = (
                    self.population[int(parents[0])][0],
                    self.population[int(parents[1])][0],
                )
                mask = self.rng.random(dimension) < 0.5
                child = np.where(mask, first, second)
                mutation = self.rng.random(dimension) < self.mutation_rate
                child[mutation] += self.rng.normal(0.0, 0.15, mutation.sum())
            suggestions.append(self._suggestion(child))
        return suggestions

    def observe(self, results: list[TrialResult]) -> None:
        super().observe(results)
        candidates = self.population + [
            (_vector(result, self), scalar_utility(result, self.directions))
            for result in results
            if result.status == "completed"
        ]
        candidates.sort(key=lambda item: item[1], reverse=True)
        self.population = candidates[: self.population_size]
        self.generation += 1

    def state_dict(self) -> dict[str, Any]:
        return {
            **self._base_state(),
            "population": [
                {"vector": vector.tolist(), "score": score}
                for vector, score in self.population
            ],
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self._load_base_state(state)
        self.population = [
            (np.asarray(item["vector"], dtype=np.float64), float(item["score"]))
            for item in state["population"]
        ]


class DifferentialEvolutionSearch(GeneticAlgorithmSearch):
    """Differential mutation and binomial crossover."""

    name = "differential_evolution"

    def __init__(
        self,
        seed: int = 1024,
        *,
        population_size: int = 10,
        differential_weight: float = 0.8,
        crossover_rate: float = 0.7,
    ) -> None:
        super().__init__(seed, population_size=population_size)
        self.differential_weight = differential_weight
        self.crossover_rate = crossover_rate

    def suggest(self, n: int = 1) -> list[TrialSuggestion]:
        dimension = self._require_space().dimension
        suggestions: list[TrialSuggestion] = []
        for _ in range(n):
            if len(self.population) < 4:
                child = self.rng.random(dimension)
            else:
                indices = self.rng.choice(len(self.population), size=4, replace=False)
                target, first, second, third = [
                    self.population[int(index)][0] for index in indices
                ]
                mutant = first + self.differential_weight * (second - third)
                crossover = self.rng.random(dimension) < self.crossover_rate
                crossover[int(self.rng.integers(0, dimension))] = True
                child = np.where(crossover, mutant, target)
            suggestions.append(self._suggestion(child))
        return suggestions


class SimulatedAnnealingSearch(BaseSearcher):
    """Single-chain simulated annealing with Metropolis acceptance."""

    name = "simulated_annealing"

    def __init__(
        self,
        seed: int = 1024,
        *,
        temperature: float = 1.0,
        cooling: float = 0.95,
        step_scale: float = 0.15,
    ) -> None:
        super().__init__(seed)
        self.temperature = temperature
        self.cooling = cooling
        self.step_scale = step_scale
        self.current: Vector | None = None
        self.current_score = -math.inf

    def suggest(self, n: int = 1) -> list[TrialSuggestion]:
        dimension = self._require_space().dimension
        suggestions: list[TrialSuggestion] = []
        for _ in range(n):
            vector = (
                self.rng.random(dimension)
                if self.current is None
                else self.current
                + self.rng.normal(0.0, self.step_scale, size=dimension)
            )
            suggestions.append(self._suggestion(vector))
        return suggestions

    def observe(self, results: list[TrialResult]) -> None:
        super().observe(results)
        for result in sorted(results, key=lambda item: item.trial_id):
            score = scalar_utility(result, self.directions)
            candidate = _vector(result, self)
            delta = score - self.current_score
            accept = (
                self.current is None
                or delta >= 0.0
                or self.rng.random()
                < math.exp(max(-700.0, delta / max(self.temperature, 1e-12)))
            )
            if accept:
                self.current = candidate
                self.current_score = score
            self.temperature = max(1e-4, self.temperature * self.cooling)
            self.generation += 1

    def state_dict(self) -> dict[str, Any]:
        return {
            **self._base_state(),
            "temperature": self.temperature,
            "current": None if self.current is None else self.current.tolist(),
            "current_score": (
                None if not math.isfinite(self.current_score) else self.current_score
            ),
        }

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self._load_base_state(state)
        self.temperature = float(state["temperature"])
        current = state["current"]
        self.current = (
            None if current is None else np.asarray(current, dtype=np.float64)
        )
        self.current_score = (
            -math.inf
            if state["current_score"] is None
            else float(state["current_score"])
        )
