"""Strict configuration for the optional read-only Phase 8 service."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlparse

import yaml
from pydantic import Field, field_validator, model_validator

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


class GUIServiceConfig(ServiceConfig):
    """Non-public, explicit loopback configuration for guarded GUI jobs."""

    execution_enabled: Literal[True] = True
    cors_origins: tuple[str, ...] = ()
    max_concurrent_jobs: int = Field(default=2, ge=1, le=8)
    max_job_log_bytes: int = Field(default=200_000, ge=4096, le=5_000_000)

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        """Allow exact HTTP(S) origins only; wildcard CORS is never accepted."""
        if len(origins) != len(set(origins)):
            raise ValueError("cors_origins must be unique")
        for origin in origins:
            parsed = urlparse(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("cors_origins must contain exact credential-free origins")
            if origin == "*":
                raise ValueError("wildcard CORS is forbidden")
        return origins

    @model_validator(mode="after")
    def require_loopback_execution(self) -> GUIServiceConfig:
        if self.host not in {
            "127.0.0.1",
            "::1",
            "localhost",
        }:
            raise ValueError("GUI execution service must bind to a loopback host")
        return self


def load_service_config(path: Path) -> ServiceConfig:
    """Load service YAML without importing FastAPI or opening a socket."""
    with path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise TypeError("service configuration must be a mapping")
    if raw.get("execution_enabled") is True:
        return GUIServiceConfig.model_validate(raw)
    return ServiceConfig.model_validate(raw)
