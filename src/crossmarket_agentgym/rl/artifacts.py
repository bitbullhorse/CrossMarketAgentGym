"""Reproducible training artifact metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TrainingMetadata(BaseModel):
    """Credential-free checkpoint provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    algorithm: str
    policy: str
    requested_timesteps: int = Field(ge=1)
    trained_timesteps: int = Field(ge=1)
    seed: int = Field(ge=0)
    config_sha256: str = Field(min_length=64, max_length=64)
    checkpoint: str
    dataset_id: str
    data_partition: str
    dependencies: dict[str, str]


@dataclass(frozen=True, slots=True)
class TrainingArtifact:
    """In-memory model plus its persisted metadata and paths."""

    model: Any
    metadata: TrainingMetadata
    run_dir: Path
    checkpoint_path: Path
