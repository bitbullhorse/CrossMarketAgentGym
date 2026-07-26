"""Strict schemas for release, quickstart, and reproduction evidence."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crossmarket_agentgym.data.dataset import DatasetValidationSummary
from crossmarket_agentgym.environments.checks import EnvironmentCheckSummary
from crossmarket_agentgym.reporting.models import RunKind


class StrictReleaseModel(BaseModel):
    """Reject release schema drift, mutation, and non-finite values."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class VerificationCheck(StrictReleaseModel):
    """One named release or reproduction assertion."""

    name: str = Field(min_length=1, max_length=100)
    passed: bool
    detail: str = Field(min_length=1, max_length=1000)


class ReproductionResult(StrictReleaseModel):
    """Read-only verification of a recorded run and deterministic replay."""

    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    kind: RunKind
    run_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    is_valid: bool
    deterministic_replay: bool
    network_used: Literal[False] = False
    account_state_mutated: Literal[False] = False
    test_metrics_used_for_selection: Literal[False] = False
    checks: tuple[VerificationCheck, ...]


class CpuQuickstartSummary(StrictReleaseModel):
    """One-command CPU sample validation and environment smoke result."""

    version: str
    is_valid: bool
    network_used: Literal[False] = False
    llm_used: Literal[False] = False
    data: DatasetValidationSummary
    environment: EnvironmentCheckSummary


class ReleaseReadinessResult(StrictReleaseModel):
    """Local pre-publish gate without an external state change."""

    version: str
    is_ready: bool
    external_publish_performed: Literal[False] = False
    checks: tuple[VerificationCheck, ...]


class DistributionArtifact(StrictReleaseModel):
    """One built distribution and its digest."""

    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)


class DistributionManifest(StrictReleaseModel):
    """Credential-free provenance for locally built distributions."""

    schema_version: Literal["1.0"] = "1.0"
    package: Literal["crossmarket-agent-gym"] = "crossmarket-agent-gym"
    version: str
    python: str
    platform: str
    source_date_epoch: int | None = Field(default=None, ge=0)
    artifacts: tuple[DistributionArtifact, ...]


class DistributionVerificationResult(StrictReleaseModel):
    """Archive-content checks before PyPI or GitHub publication."""

    version: str
    is_valid: bool
    checks: tuple[VerificationCheck, ...]


class ContractFreezeResult(StrictReleaseModel):
    """API and Schema freeze export or verification result."""

    schema_version: Literal["1.0"] = "1.0"
    release: str
    api_records: int = Field(ge=1)
    config_schemas: int = Field(ge=1)
    artifact_schemas: int = Field(ge=1)
    is_valid: bool
    wrote_files: bool
    checks: tuple[VerificationCheck, ...]
