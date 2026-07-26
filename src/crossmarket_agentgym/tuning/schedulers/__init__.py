"""Independent TrialScheduler implementations."""

from crossmarket_agentgym.tuning.schedulers.algorithms import (
    ASHAScheduler,
    FIFOScheduler,
    HyperBandScheduler,
    MedianStoppingScheduler,
    PopulationBasedTrainingScheduler,
)
from crossmarket_agentgym.tuning.schedulers.base import (
    DecisionAction,
    TrialDecision,
    TrialScheduler,
)

SCHEDULERS = {
    "fifo": FIFOScheduler,
    "median": MedianStoppingScheduler,
    "asha": ASHAScheduler,
    "hyperband": HyperBandScheduler,
    "pbt": PopulationBasedTrainingScheduler,
}

SEARCHER_SCHEDULER_COMPATIBILITY: dict[str, frozenset[str]] = {
    "random": frozenset(SCHEDULERS),
    "grid": frozenset({"fifo", "median", "asha", "hyperband"}),
    "tpe": frozenset(SCHEDULERS),
    "cma_es": frozenset(SCHEDULERS),
    "nsga_ii": frozenset(SCHEDULERS),
    "pso": frozenset(SCHEDULERS),
    "genetic": frozenset(SCHEDULERS),
    "differential_evolution": frozenset(SCHEDULERS),
    "simulated_annealing": frozenset({"fifo", "median", "asha", "hyperband"}),
}


def ensure_compatible(searcher: str, scheduler: str) -> None:
    """Reject unsupported searcher–scheduler combinations."""
    allowed = SEARCHER_SCHEDULER_COMPATIBILITY.get(searcher)
    if allowed is None:
        raise ValueError(f"unknown searcher: {searcher}")
    if scheduler not in allowed:
        raise ValueError(f"scheduler {scheduler} is incompatible with {searcher}")


__all__ = [
    "SCHEDULERS",
    "SEARCHER_SCHEDULER_COMPATIBILITY",
    "ASHAScheduler",
    "DecisionAction",
    "FIFOScheduler",
    "HyperBandScheduler",
    "MedianStoppingScheduler",
    "PopulationBasedTrainingScheduler",
    "TrialDecision",
    "TrialScheduler",
    "ensure_compatible",
]
