"""Auditable Phase 6 CLI workflow around the shared AgentRuntime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from crossmarket_agentgym.agents.models import AgentRuntimeConfig, TeamRunResult
from crossmarket_agentgym.agents.roles import AgentRegistry
from crossmarket_agentgym.agents.runtime import AgentRuntime
from crossmarket_agentgym.agents.tools import ToolRegistry
from crossmarket_agentgym.audit import write_run_manifest
from crossmarket_agentgym.audit.logging import redact_value


def _inside_workspace(path: Path, root: Path) -> Path:
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise PermissionError("Agent runtime path leaves workspace_root")
    return resolved


def execute_agent_runtime(
    config: AgentRuntimeConfig,
    *,
    registry: AgentRegistry | None = None,
    tool_registry: ToolRegistry | None = None,
) -> TeamRunResult:
    """Execute a single or team run without silently replacing any Provider."""
    workspace = config.workspace_root.resolve()
    output_root = _inside_workspace(config.output_dir, workspace)
    run_dir = output_root / config.run_id
    if run_dir.exists():
        raise FileExistsError(f"Agent runtime run already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    safe_config = redact_value(config.model_dump(mode="json"))
    config_text = yaml.safe_dump(
        safe_config,
        allow_unicode=True,
        sort_keys=True,
    )
    (run_dir / "config.resolved.yaml").write_text(
        config_text,
        encoding="utf-8",
        newline="\n",
    )
    (run_dir / "config.sha256").write_text(
        hashlib.sha256(config_text.encode()).hexdigest() + "\n",
        encoding="utf-8",
        newline="\n",
    )

    runtime = AgentRuntime(
        config,
        run_dir=run_dir,
        registry=registry,
        tool_registry=tool_registry,
    )
    try:
        result = runtime.run()
    finally:
        runtime.close()
    (run_dir / "runtime_summary.json").write_text(
        json.dumps(
            result.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    write_run_manifest(
        run_dir,
        workspace_root=workspace,
        run_id=config.run_id,
        kind="agent",
        config_path=run_dir / "config.resolved.yaml",
        seed=config.seed,
    )
    return result
