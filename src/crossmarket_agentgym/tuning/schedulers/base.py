"""Independent TrialScheduler protocol and decisions."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

DecisionAction = Literal["continue", "stop", "pause", "promote", "exploit"]


class TrialDecision(BaseModel):
    """Resource decision emitted without suggesting a new trial."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: DecisionAction
    reason: str
    source_trial_id: int | None = Field(default=None, ge=0)
    parameter_patch: dict[str, Any] = Field(default_factory=dict)


class TrialScheduler(Protocol):
    """Resource scheduling interface separate from SearchAlgorithm."""

    name: str

    def on_trial_add(self, trial_id: int) -> None:
        """Register a new trial."""
        ...

    def on_result(
        self,
        trial_id: int,
        resource: float,
        metric: float,
        parameters: dict[str, Any] | None = None,
    ) -> TrialDecision:
        """Return a resource decision from an intermediate metric."""
        ...

    def on_complete(self, trial_id: int, metric: float | None = None) -> None:
        """Record terminal status."""
        ...

    def state_dict(self) -> dict[str, Any]:
        """Return JSON-compatible state."""
        ...

    def load_state_dict(self, state: dict[str, Any]) -> None:
        """Restore JSON-compatible state."""
        ...
