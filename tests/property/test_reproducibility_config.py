"""Property tests for deterministic seed boundaries."""

from hypothesis import given
from hypothesis import strategies as st

from crossmarket_agentgym.config import ProjectConfig


@given(st.integers(min_value=0, max_value=2**32 - 1))
def test_every_supported_seed_round_trips(seed: int) -> None:
    """Every accepted seed is preserved exactly."""
    assert ProjectConfig(seed=seed).seed == seed
