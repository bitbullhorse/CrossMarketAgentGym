"""Package-level smoke tests."""

from crossmarket_agentgym import __version__


def test_version_is_exposed() -> None:
    """The import package exposes the same development version as metadata."""
    assert __version__ == "0.1.0"
