"""Regression test for search, scheduling, and execution separation."""

from crossmarket_agentgym.tuning import executors, schedulers, searchers


def test_searchers_and_schedulers_are_distinct_modules() -> None:
    """Resource schedulers cannot be imported as search algorithms."""
    assert schedulers.__name__.endswith(".schedulers")
    assert searchers.__name__.endswith(".searchers")
    assert schedulers is not searchers
    assert executors.__name__.endswith(".executors")
    assert executors is not schedulers
    assert executors is not searchers
