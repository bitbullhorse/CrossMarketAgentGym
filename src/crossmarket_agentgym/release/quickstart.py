"""Installed-wheel and source-tree CPU quickstart."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from crossmarket_agentgym import __version__
from crossmarket_agentgym.data.dataset import validate_manifest_dataset
from crossmarket_agentgym.environments.checks import (
    load_environment_check_config,
    run_environment_checks,
)
from crossmarket_agentgym.release.models import CpuQuickstartSummary


def _quickstart_paths(workspace_root: Path) -> tuple[Path, Path]:
    workspace = workspace_root.resolve()
    source_data = workspace / "data" / "sample"
    source_config = workspace / "configs" / "env" / "cross_market.yaml"
    if source_data.is_dir() and source_config.is_file():
        return source_data, source_config
    package_root = Path(str(resources.files("crossmarket_agentgym")))
    packaged = package_root / "resources"
    data_root = packaged / "data" / "sample"
    config_path = packaged / "configs" / "env" / "cross_market.yaml"
    if not data_root.is_dir() or not config_path.is_file():
        raise FileNotFoundError("packaged CPU quickstart resources are unavailable")
    return data_root, config_path


def run_cpu_quickstart(
    workspace_root: str | Path = ".",
    *,
    smoke_steps: int = 64,
) -> CpuQuickstartSummary:
    """Validate the four-market sample and run seeded environment checks."""
    data_root, env_config_path = _quickstart_paths(Path(workspace_root))
    data_summary = validate_manifest_dataset(data_root)
    env_config = load_environment_check_config(env_config_path).model_copy(
        update={"dataset_root": data_root, "smoke_steps": smoke_steps}
    )
    environment_summary = run_environment_checks(env_config)
    return CpuQuickstartSummary(
        version=__version__,
        is_valid=data_summary.is_valid and environment_summary.is_valid,
        data=data_summary,
        environment=environment_summary,
    )
