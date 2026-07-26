"""Distribution metadata regression tests."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parents[2]


def test_distribution_import_and_cli_names_remain_stable() -> None:
    """Published names must not drift independently."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as stream:
        metadata: dict[str, Any] = tomllib.load(stream)

    assert metadata["project"]["name"] == "crossmarket-agent-gym"
    assert metadata["project"]["scripts"]["cmag"] == "crossmarket_agentgym.cli.app:main"
    assert metadata["project"]["requires-python"] == ">=3.11,<3.13"
    assert metadata["project"]["dynamic"] == ["version"]
    assert metadata["tool"]["hatch"]["version"]["path"].endswith("_version.py")
