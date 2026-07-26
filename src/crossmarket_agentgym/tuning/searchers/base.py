"""Common SearchAlgorithm protocol and deterministic unit-vector helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from crossmarket_agentgym.tuning.models import (
    Direction,
    SearchSpace,
    StudyState,
    TrialResult,
    TrialSuggestion,
)


class SearchAlgorithm(Protocol):
    """Searcher interface kept separate from resource schedulers."""

    name: str

    def initialize(self, search_space: SearchSpace, study_state: StudyState) -> None:
        """Bind a space and any completed study history."""
        ...

    def suggest(self, n: int = 1) -> list[TrialSuggestion]:
        """Suggest up to `n` candidates."""
        ...

    def observe(self, results: list[TrialResult]) -> None:
        """Update search state from terminal trial results."""
        ...

    def state_dict(self) -> dict[str, Any]:
        """Return JSON-compatible resumable state."""
        ...

    def load_state_dict(self, state: dict[str, Any]) -> None:
        """Restore state after initialization."""
        ...


class BaseSearcher(ABC):
    """Seeded base class for all concrete search algorithms."""

    name = "base"

    def __init__(self, seed: int = 1024) -> None:
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.space: SearchSpace | None = None
        self.directions: tuple[Direction, ...] = ("maximize",)
        self.results: list[TrialResult] = []
        self._counter = 0
        self.generation = 0

    def initialize(self, search_space: SearchSpace, study_state: StudyState) -> None:
        """Bind space/history and advance trial IDs past stored results."""
        self.space = search_space
        self.directions = study_state.directions
        self.results = list(study_state.results)
        self._counter = (
            max((result.trial_id for result in self.results), default=-1) + 1
        )

    def _require_space(self) -> SearchSpace:
        if self.space is None:
            raise RuntimeError("searcher must be initialized")
        return self.space

    def _valid_vector(
        self,
        vector: NDArray[np.floating[Any]],
    ) -> tuple[NDArray[np.float64], dict[str, Any]]:
        """Clip and decode, falling back to bounded random constraint repair."""
        space = self._require_space()
        clipped = np.clip(np.asarray(vector, dtype=np.float64), 0.0, 1.0)
        try:
            return clipped, space.decode(clipped)
        except ValueError:
            candidate = space.sample(self.rng)
            return space.encode(candidate), candidate

    def _suggestion(
        self,
        vector: NDArray[np.floating[Any]],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> TrialSuggestion:
        """Allocate one stable trial ID from a unit vector."""
        valid, candidate = self._valid_vector(vector)
        trial_id = self._counter
        self._counter += 1
        details = dict(metadata or {})
        details["unit_vector"] = valid.tolist()
        return TrialSuggestion(
            trial_id=trial_id,
            parameters=candidate,
            generation=self.generation,
            metadata=details,
        )

    def observe(self, results: list[TrialResult]) -> None:
        """Retain results in trial order for reports and adaptive search."""
        space = self._require_space()
        for result in results:
            space.validate_candidate(result.parameters)
        self.results.extend(results)
        self.results.sort(key=lambda item: item.trial_id)

    def _base_state(self) -> dict[str, Any]:
        """Return state shared by every concrete algorithm."""
        return {
            "name": self.name,
            "seed": self.seed,
            "counter": self._counter,
            "generation": self.generation,
            "rng_state": self.rng.bit_generator.state,
        }

    def _load_base_state(self, state: dict[str, Any]) -> None:
        """Restore and validate common state."""
        self._require_space()
        if state.get("name") != self.name:
            raise ValueError("searcher state belongs to a different algorithm")
        self._counter = int(state["counter"])
        self.generation = int(state["generation"])
        self.rng.bit_generator.state = state["rng_state"]

    @abstractmethod
    def suggest(self, n: int = 1) -> list[TrialSuggestion]:
        """Suggest candidates."""

    def state_dict(self) -> dict[str, Any]:
        """Return common resumable state."""
        return self._base_state()

    def load_state_dict(self, state: dict[str, Any]) -> None:
        """Restore common resumable state."""
        self._load_base_state(state)
