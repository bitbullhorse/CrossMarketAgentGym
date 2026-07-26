"""Strict configuration for the optional read-only Phase 8 service."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import yaml
from pydantic import Field, model_validator

from crossmarket_agentgym.reporting.models import StrictReportModel


class ServiceConfig(StrictReportModel):
    """Local-first service settings with explicit remote opt-in."""

    workspace_root: Path = Field(default=cast(Path, "."), validate_default=True)
    runs_root: Path = Field(default=cast(Path, "runs"), validate_default=True)
    reports_root: Path = Field(default=cast(Path, "reports"), validate_default=True)
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    allow_remote: bool = False
    docs_enabled: bool = False
    max_runs: int = Field(default=500, ge=1, le=5000)
    max_json_bytes: int = Field(default=5_000_000, ge=1024, le=100_000_000)

    @model_validator(mode="after")
    def require_remote_opt_in(self) -> ServiceConfig:
        if self.host not in {"127.0.0.1", "::1", "localhost"} and not self.allow_remote:
            raise ValueError("non-loopback service host requires allow_remote=true")
        return self


def load_service_config(path: Path) -> ServiceConfig:
    """Load service YAML without importing FastAPI or opening a socket."""
    with path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("service configuration must be a mapping")
    return ServiceConfig.model_validate(raw)
