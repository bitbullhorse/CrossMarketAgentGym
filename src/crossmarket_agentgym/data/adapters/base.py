"""Common source-adapter contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd


@dataclass(frozen=True, slots=True)
class AdapterResult:
    """Canonical rows plus explicit adapter warnings and errors."""

    frame: pd.DataFrame
    source_path: Path
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        """Return true when source normalization produced no adapter errors."""
        return not self.errors


class SourceAdapter(Protocol):
    """Normalize a source file without mutating it or dropping invalid rows."""

    def load(self, path: Path) -> AdapterResult:
        """Read one source artifact into canonical columns."""
        ...
