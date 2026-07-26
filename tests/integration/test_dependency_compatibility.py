"""Compatibility smoke test for every Phase 0 runtime dependency."""

from __future__ import annotations

import sys

import gymnasium
import jinja2
import numpy
import pandas
import pyarrow
import pydantic
import rich
import typer
import yaml


def test_supported_python_runtime() -> None:
    """The package is exercised only on its declared Python line."""
    assert (3, 11) <= sys.version_info[:2] < (3, 13)


def test_core_dependencies_import_together() -> None:
    """Scientific, schema, CLI, and rendering dependencies coexist."""
    imported = (gymnasium, jinja2, numpy, pandas, pyarrow, pydantic, rich, typer, yaml)

    assert all(module is not None for module in imported)
    assert pydantic.VERSION.startswith("2.")
    assert int(numpy.__version__.split(".", maxsplit=1)[0]) < 3
