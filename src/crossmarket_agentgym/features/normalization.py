"""Train-only feature standardization with an explicit fit capability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from crossmarket_agentgym.data.partitions import PartitionCapability, require_partition


@dataclass(frozen=True, slots=True)
class StandardizationState:
    """Serializable feature statistics learned from training data only."""

    mean: NDArray[np.float64]
    scale: NDArray[np.float64]
    dataset_id: str


class TrainOnlyStandardizer:
    """Fit standardization statistics only with a training capability."""

    def __init__(self, epsilon: float = 1e-8) -> None:
        """Create an unfitted transformer."""
        if epsilon <= 0.0:
            raise ValueError("epsilon must be positive")
        self.epsilon = epsilon
        self._state: StandardizationState | None = None

    @property
    def state(self) -> StandardizationState:
        """Return fitted statistics or fail before fit."""
        if self._state is None:
            raise RuntimeError("standardizer is not fitted")
        return self._state

    def fit(
        self,
        values: NDArray[np.floating[Any]],
        capability: PartitionCapability,
    ) -> TrainOnlyStandardizer:
        """Fit the last feature axis and reject validation/test capabilities."""
        require_partition(capability, frozenset({"train"}))
        array = np.asarray(values, dtype=np.float64)
        if array.ndim < 2 or not np.isfinite(array).all():
            raise ValueError("fit values must be a finite array with a feature axis")
        axes = tuple(range(array.ndim - 1))
        mean = array.mean(axis=axes)
        scale = array.std(axis=axes, ddof=0)
        scale = np.where(scale < self.epsilon, 1.0, scale)
        self._state = StandardizationState(
            mean=np.asarray(mean, dtype=np.float64),
            scale=np.asarray(scale, dtype=np.float64),
            dataset_id=capability.dataset_id,
        )
        return self

    def transform(
        self,
        values: NDArray[np.floating[Any]],
        capability: PartitionCapability,
    ) -> NDArray[np.float64]:
        """Transform the same dataset without changing fitted statistics."""
        state = self.state
        if capability.dataset_id != state.dataset_id:
            raise ValueError("capability dataset does not match fitted statistics")
        array = np.asarray(values, dtype=np.float64)
        if array.shape[-1] != state.mean.shape[0]:
            raise ValueError("feature axis does not match fitted statistics")
        return (array - state.mean) / state.scale
