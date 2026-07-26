"""Safe YAML configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from crossmarket_agentgym.config.models import RootConfig


def load_config(path: Path) -> RootConfig:
    """Load and validate a YAML file without executable YAML extensions."""
    with path.open(encoding="utf-8") as stream:
        raw: Any = yaml.safe_load(stream)
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise TypeError("root configuration must be a mapping")
    return RootConfig.model_validate(raw)
