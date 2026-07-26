"""Strict configuration for Phase 1 dataset validation."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from crossmarket_agentgym.data.schemas import Market

DatasetLayout = Literal["canonical_manifest", "legacy_mixed"]


class DatasetConfig(BaseModel):
    """One canonical or mixed legacy dataset reference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    root: Path
    layout: DatasetLayout
    markets: dict[str, Market] = Field(default_factory=dict)
    mutation_policy: Literal["reject"] = "reject"
    max_files_per_market: int | None = Field(default=None, ge=1)


class DataValidationConfig(BaseModel):
    """Root model for `cmag data validate`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset: DatasetConfig


def load_data_config(path: Path) -> DataValidationConfig:
    """Safely load and strictly validate a data configuration."""
    with path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("data configuration root must be a mapping")
    return DataValidationConfig.model_validate(raw)
