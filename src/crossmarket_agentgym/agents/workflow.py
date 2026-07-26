"""Executable Phase 5 offline provider/tool/replay acceptance workflow."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from crossmarket_agentgym.agents.config import (
    ProviderCheckConfig,
    ProviderCheckOutput,
)
from crossmarket_agentgym.agents.providers import (
    ReplayJournal,
    ReplayProvider,
    create_provider,
)
from crossmarket_agentgym.agents.session import ProviderToolSession
from crossmarket_agentgym.agents.tools import (
    ToolExecutor,
    build_builtin_tool_registry,
)
from crossmarket_agentgym.audit.agent import AgentAuditWriter


class ProviderCheckRunSummary(BaseModel):
    """Serializable result of the Phase 5 acceptance command."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    run_dir: str
    provider: str
    model: str
    used_fallback: bool
    rounds: int
    tool_calls: int
    replay_verified: bool
    network_used: bool
    output: ProviderCheckOutput


def _inside_workspace(path: Path, root: Path) -> Path:
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise PermissionError("provider run path leaves workspace_root")
    return resolved


def execute_provider_check(config: ProviderCheckConfig) -> ProviderCheckRunSummary:
    """Run one schema/tool conversation and verify its offline replay."""
    workspace = config.workspace_root.resolve()
    output_root = _inside_workspace(config.output_dir, workspace)
    run_dir = output_root / config.run_id
    summary_path = run_dir / "provider_check_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"provider check run already exists: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    provider = create_provider(
        config.provider,
        mock_script=config.mock_script if config.provider.provider == "mock" else None,
    )
    registry = build_builtin_tool_registry(workspace)
    executor = ToolExecutor(registry, config.tool_policy, workspace)
    audit = AgentAuditWriter(
        run_dir,
        provider_config=config.provider.model_dump(mode="json"),
        prompt_version=config.prompt_version,
    )
    journal_path = run_dir / "agent" / "replay.jsonl"
    outcome = ProviderToolSession(
        provider=provider,
        tool_executor=executor,
        audit=audit,
        replay_journal=ReplayJournal(journal_path),
        max_rounds=config.max_rounds,
    ).run(
        list(config.messages),
        response_schema=ProviderCheckOutput,
        fallback=config.fallback,
        generation_config=config.provider.generation,
        tool_names=list(config.tool_names),
    )
    close = getattr(provider, "close", None)
    if callable(close):
        close()

    replay_verified = False
    if config.verify_replay and not outcome.used_fallback:
        replay_executor = ToolExecutor(
            build_builtin_tool_registry(workspace),
            config.tool_policy,
            workspace,
        )
        replay_outcome = ProviderToolSession(
            provider=ReplayProvider(journal_path, model=config.provider.model),
            tool_executor=replay_executor,
            audit=AgentAuditWriter(
                run_dir / "replay_verification",
                provider_config={
                    "provider": "replay",
                    "model": config.provider.model,
                    "replay_path": str(journal_path),
                },
                prompt_version=config.prompt_version,
            ),
            max_rounds=config.max_rounds,
        ).run(
            list(config.messages),
            response_schema=ProviderCheckOutput,
            fallback=config.fallback,
            generation_config=config.provider.generation,
            tool_names=list(config.tool_names),
        )
        replay_verified = (
            not replay_outcome.used_fallback
            and replay_outcome.value == outcome.value
        )
    summary = ProviderCheckRunSummary(
        run_id=config.run_id,
        run_dir=str(run_dir),
        provider=config.provider.provider,
        model=config.provider.model,
        used_fallback=outcome.used_fallback,
        rounds=outcome.rounds,
        tool_calls=executor.total_calls,
        replay_verified=replay_verified,
        network_used=config.provider.provider == "openai_compatible",
        output=outcome.value,
    )
    summary_path.write_text(
        json.dumps(
            summary.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return summary
