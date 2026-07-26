"""Release readiness, CPU quickstart, and read-only reproduction APIs."""

from crossmarket_agentgym.release.checks import check_release_readiness
from crossmarket_agentgym.release.distribution import verify_distributions
from crossmarket_agentgym.release.manifest import build_release_manifest
from crossmarket_agentgym.release.quickstart import run_cpu_quickstart
from crossmarket_agentgym.release.reproduction import reproduce_run
from crossmarket_agentgym.release.versioning import (
    is_release_candidate,
    release_label,
    release_tag,
)

__all__ = [
    "build_release_manifest",
    "check_release_readiness",
    "reproduce_run",
    "run_cpu_quickstart",
    "verify_distributions",
    "is_release_candidate",
    "release_label",
    "release_tag",
]
