"""Deterministic local reference executor."""

from __future__ import annotations

from crossmarket_agentgym.tuning.executors.base import (
    ObjectiveEvaluator,
    evaluate_safely,
)
from crossmarket_agentgym.tuning.models import TrialResult, TrialSuggestion


class LocalTrialExecutor:
    """Evaluate in configuration order on the current process."""

    name = "local"

    def evaluate(
        self,
        suggestions: list[TrialSuggestion],
        evaluator: ObjectiveEvaluator,
    ) -> list[TrialResult]:
        """Evaluate every suggestion and preserve its original order."""
        return [evaluate_safely(evaluator, suggestion) for suggestion in suggestions]

    def close(self) -> None:
        """The local executor owns no external resource."""
