"""Immutable dataset-manifest models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FileRole = Literal["ohlcv", "instruments", "fx"]


class ManifestFile(BaseModel):
    """Integrity and semantic metadata for one dataset artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    role: FileRole
    format: Literal["csv", "parquet"]
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_count: int = Field(ge=0)
    markets: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    date_start: str | None = None
    date_end: str | None = None


class QualitySummary(BaseModel):
    """Aggregated validation status captured at import time."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    is_valid: bool
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)


class DatasetManifest(BaseModel):
    """Reproducible metadata for a canonical dataset root."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0.0"
    dataset_name: str
    created_at: datetime
    software_version: str
    source: str
    adjustment_rule: str
    row_count: int = Field(ge=0)
    markets: list[str]
    symbols: list[str]
    date_start: str | None
    date_end: str | None
    schema_columns: list[str]
    files: list[ManifestFile]
    quality: QualitySummary


class ManifestVerification(BaseModel):
    """Recomputed filesystem integrity results."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    missing_files: list[str] = Field(default_factory=list)
    hash_mismatches: list[str] = Field(default_factory=list)
    size_mismatches: list[str] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return true only when every recorded artifact matches."""
        return not (self.missing_files or self.hash_mismatches or self.size_mismatches)
