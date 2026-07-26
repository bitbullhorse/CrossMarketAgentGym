"""Unified trial execution over independent searchers and schedulers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from crossmarket_agentgym.tuning.executors import LocalTrialExecutor, TrialBatchExecutor
from crossmarket_agentgym.tuning.executors.base import ObjectiveEvaluator
from crossmarket_agentgym.tuning.models import (
    Direction,
    SearchSpace,
    StudyState,
    TrialResult,
    TrialSuggestion,
)
from crossmarket_agentgym.tuning.schedulers.base import TrialScheduler
from crossmarket_agentgym.tuning.searchers.base import SearchAlgorithm
from crossmarket_agentgym.tuning.store import SQLiteStudyStore


class FunctionalObjective:
    """Adapt a pure callable to the objective evaluator contract."""

    def __init__(
        self,
        function: Callable[[dict[str, Any]], float | tuple[float, ...]],
        *,
        resource: float = 1.0,
    ) -> None:
        self.function = function
        self.resource = resource

    def evaluate(self, suggestion: TrialSuggestion) -> TrialResult:
        """Evaluate and normalize a scalar or objective tuple."""
        raw = self.function(suggestion.parameters)
        objectives = (float(raw),) if isinstance(raw, int | float) else tuple(raw)
        return TrialResult(
            trial_id=suggestion.trial_id,
            parameters=suggestion.parameters,
            status="completed",
            objectives=objectives,
            metrics={"objective": objectives[0]},
            resource=self.resource,
        )


class TrialRunner:
    """Persisted CPU-first driver shared by every search/scheduler pairing."""

    def __init__(
        self,
        *,
        study_name: str,
        directions: tuple[Direction, ...],
        search_space: SearchSpace,
        searcher: SearchAlgorithm,
        scheduler: TrialScheduler,
        evaluator: ObjectiveEvaluator,
        store: SQLiteStudyStore,
        batch_size: int = 1,
        study_metadata: dict[str, Any] | None = None,
        executor: TrialBatchExecutor | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.study_name = study_name
        self.directions = directions
        self.search_space = search_space
        self.searcher = searcher
        self.scheduler = scheduler
        self.evaluator = evaluator
        self.store = store
        self.batch_size = batch_size
        self.study_metadata = study_metadata
        self.executor = executor or LocalTrialExecutor()
        self._initialized = False

    def _initialize(self) -> None:
        if self._initialized:
            return
        state = self.store.create_study(
            self.study_name,
            self.directions,
            self.study_metadata,
        )
        self.searcher.initialize(self.search_space, state)
        searcher_checkpoint = self.store.load_checkpoint(
            self.study_name,
            "searcher",
        )
        if searcher_checkpoint is not None:
            self.searcher.load_state_dict(searcher_checkpoint)
        scheduler_checkpoint = self.store.load_checkpoint(
            self.study_name,
            "scheduler",
        )
        if scheduler_checkpoint is not None:
            self.scheduler.load_state_dict(scheduler_checkpoint)
        self._initialized = True

    def _checkpoint(self) -> None:
        self.store.save_checkpoint(
            self.study_name,
            "searcher",
            self.searcher.state_dict(),
        )
        self.store.save_checkpoint(
            self.study_name,
            "scheduler",
            self.scheduler.state_dict(),
        )

    def _evaluate_batch(
        self,
        suggestions: list[TrialSuggestion],
    ) -> list[TrialResult]:
        for suggestion in suggestions:
            self.scheduler.on_trial_add(suggestion.trial_id)
        results = self.executor.evaluate(suggestions, self.evaluator)
        if len(results) != len(suggestions):
            raise ValueError("executor returned an unexpected result count")
        for suggestion, result in zip(suggestions, results, strict=True):
            if (
                result.trial_id != suggestion.trial_id
                or result.parameters != suggestion.parameters
            ):
                raise ValueError("executor returned a mismatched trial result")
            self.store.save_result(self.study_name, result)
            if result.status == "completed":
                metric = result.objectives[0]
                self.scheduler.on_result(
                    suggestion.trial_id,
                    result.resource,
                    metric,
                    dict(suggestion.parameters),
                )
                self.scheduler.on_complete(suggestion.trial_id, metric)
            else:
                self.scheduler.on_complete(suggestion.trial_id)
        self.searcher.observe(results)
        self._checkpoint()
        return results

    def run(self, max_trials: int) -> StudyState:
        """Resume then execute until the study has `max_trials` terminal records."""
        if max_trials < 1:
            raise ValueError("max_trials must be positive")
        self._initialize()
        terminal = self.store.study_state(self.study_name)
        pending = self.store.pending_suggestions(self.study_name)
        if pending:
            self._evaluate_batch(pending)
            terminal = self.store.study_state(self.study_name)

        while len(terminal.results) < max_trials:
            count = min(self.batch_size, max_trials - len(terminal.results))
            suggestions = self.searcher.suggest(count)
            if not suggestions:
                break
            for suggestion in suggestions:
                self.store.save_suggestion(self.study_name, suggestion)
            self._checkpoint()
            self._evaluate_batch(suggestions)
            terminal = self.store.study_state(self.study_name)
        return terminal
