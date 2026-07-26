"""Executor boundary kept independent from searchers and schedulers."""

from __future__ import annotations

from typing import Protocol

from crossmarket_agentgym.tuning.models import TrialResult, TrialSuggestion


class ObjectiveEvaluator(Protocol):
    """Serializable or local objective evaluation boundary."""

    def evaluate(self, suggestion: TrialSuggestion) -> TrialResult:
        """Evaluate one suggestion without hidden test authority."""
        ...


class TrialBatchExecutor(Protocol):
    """Evaluate suggestions without generating or scheduling them."""

    name: str

    def evaluate(
        self,
        suggestions: list[TrialSuggestion],
        evaluator: ObjectiveEvaluator,
    ) -> list[TrialResult]:
        """Return one result per suggestion in the original order."""
        ...

    def close(self) -> None:
        """Release executor-owned resources."""
        ...


def evaluate_safely(
    evaluator: ObjectiveEvaluator,
    suggestion: TrialSuggestion,
) -> TrialResult:
    """Convert an objective exception into a persisted failed Trial."""
    try:
        result = evaluator.evaluate(suggestion)
        if (
            result.trial_id != suggestion.trial_id
            or result.parameters != suggestion.parameters
        ):
            raise ValueError("evaluator returned a mismatched trial result")
        return result
    except Exception as error:  # trial failure must not abort the study
        return TrialResult(
            trial_id=suggestion.trial_id,
            parameters=suggestion.parameters,
            status="failed",
            error=f"{error.__class__.__name__}: {error}",
        )
