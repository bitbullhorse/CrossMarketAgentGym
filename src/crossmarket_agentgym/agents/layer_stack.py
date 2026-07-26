"""Phase 7 three-layer orchestration, hard-policy fusion, and directive Replay."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import Field

from crossmarket_agentgym.agents.directives import (
    AdministratorRiskPolicy,
    ConstraintFusionResult,
    DirectiveProjection,
    HierarchicalDirective,
    ResearchDirective,
    RiskDirective,
    RiskMergeResult,
    StrictDirectiveModel,
    cadence_due,
    fuse_constraint_directives,
    merge_risk_directive,
    project_with_directives,
    static_hierarchical_fallback,
    static_research_fallback,
    static_risk_fallback,
)
from crossmarket_agentgym.agents.layer_config import Phase7RunConfig
from crossmarket_agentgym.agents.models import (
    AgentDecision,
    AgentRuntimeConfig,
    TeamRunResult,
    TeamSpec,
)
from crossmarket_agentgym.agents.roles import AgentRegistry
from crossmarket_agentgym.agents.runtime import AgentRuntime
from crossmarket_agentgym.agents.tools import ToolRegistry, build_builtin_tool_registry
from crossmarket_agentgym.audit.directives import (
    DirectiveJournal,
    load_directive_journal,
)
from crossmarket_agentgym.audit.logging import redact_value
from crossmarket_agentgym.audit.run_manifest import write_run_manifest
from crossmarket_agentgym.data.schemas import Market
from crossmarket_agentgym.environments.config import EnvironmentConfig

DirectiveSource = Literal["agent", "fallback", "previous", "disabled"]


class ResearchLayerResult(StrictDirectiveModel):
    enabled: bool
    source: DirectiveSource
    directive: ResearchDirective | None
    team: TeamRunResult | None = None


class RiskLayerResult(StrictDirectiveModel):
    enabled: bool
    due: bool
    source: DirectiveSource
    directive: RiskDirective | None
    merge: RiskMergeResult
    team: TeamRunResult | None = None


class HierarchicalLayerResult(StrictDirectiveModel):
    enabled: bool
    due: bool
    source: DirectiveSource
    directive: HierarchicalDirective | None
    team: TeamRunResult | None = None


class Phase7RunSummary(StrictDirectiveModel):
    """Terminal result for all layer presets, including no-LLM."""

    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    preset: str
    provider_runtimes_started: int = Field(ge=0, le=3)
    network_used: bool
    research: ResearchLayerResult
    risk: RiskLayerResult
    hierarchical: HierarchicalLayerResult
    fusion: ConstraintFusionResult
    projection: DirectiveProjection
    directive_replay_verified: bool


class Phase7ReplayBundle(StrictDirectiveModel):
    """Minimal validated state needed to reproduce directive fusion without an LLM."""

    schema_version: Literal["1.0"] = "1.0"
    environment: EnvironmentConfig
    markets: tuple[Market, ...]
    raw_action: tuple[float, ...]
    current_weights: tuple[float, ...]
    tradable_mask: tuple[bool, ...]
    risk_mode: Literal["advisory", "enforced"]
    risk_proposed: RiskDirective | None
    hierarchical: HierarchicalDirective | None
    research: ResearchDirective | None


def _inside_workspace(path: Path, root: Path) -> Path:
    resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise PermissionError("Phase 7 run path leaves workspace_root")
    return resolved


def _run_team(
    config: Phase7RunConfig,
    *,
    layer: str,
    team: TeamSpec,
    payload: dict[str, Any],
    run_dir: Path,
    registry: AgentRegistry | None,
    tool_registry: ToolRegistry,
) -> TeamRunResult:
    runtime_config = AgentRuntimeConfig(
        run_id=f"{config.run_id}.{layer}",
        workspace_root=config.workspace_root,
        output_dir=config.output_dir,
        prompt_version=config.prompt_version,
        seed=config.seed,
        objective=config.objective,
        payload=payload,
        load_entry_points=config.load_entry_points,
        team=team,
    )
    runtime = AgentRuntime(
        runtime_config,
        run_dir=run_dir / "layers" / layer,
        registry=registry,
        tool_registry=tool_registry,
    )
    try:
        return runtime.run()
    finally:
        runtime.close()


def _payload_model(
    decision: AgentDecision,
    key: str,
    model: type[StrictDirectiveModel],
) -> StrictDirectiveModel | None:
    raw = decision.payload.get(key)
    if not isinstance(raw, dict):
        return None
    return model.model_validate(raw)


def _research_layer(
    config: Phase7RunConfig,
    *,
    run_dir: Path,
    registry: AgentRegistry | None,
    tool_registry: ToolRegistry,
) -> ResearchLayerResult:
    layer = config.layers.research
    if not layer.enabled:
        return ResearchLayerResult(enabled=False, source="disabled", directive=None)
    assert layer.team is not None
    team = _run_team(
        config,
        layer="research",
        team=layer.team,
        payload={
            **config.research_payload,
            "research_mode": layer.mode,
            "partition_authority": "validation_only",
        },
        run_dir=run_dir,
        registry=registry,
        tool_registry=tool_registry,
    )
    parsed = _payload_model(
        team.aggregate.decision,
        "research_directive",
        ResearchDirective,
    )
    directive = (
        parsed
        if isinstance(parsed, ResearchDirective)
        else static_research_fallback(layer.mode, config.objective)
    )
    fallback = static_research_fallback(layer.mode, config.objective)
    return ResearchLayerResult(
        enabled=True,
        source=(
            "fallback"
            if not isinstance(parsed, ResearchDirective)
            or (team.fallback > 0 and directive == fallback)
            else "agent"
        ),
        directive=directive,
        team=team,
    )


def _risk_from_aggregate(
    decision: AgentDecision,
    fallback: RiskDirective,
) -> RiskDirective:
    parsed = _payload_model(decision, "risk_directive", RiskDirective)
    if not isinstance(parsed, RiskDirective):
        return fallback
    constraints = decision.constraints
    return parsed.model_copy(
        update={
            "cash_floor": (
                constraints.cash_floor
                if constraints.cash_floor is not None
                else parsed.cash_floor
            ),
            "max_asset_weight": max(
                1e-12,
                (
                    constraints.max_asset_weight
                    if constraints.max_asset_weight is not None
                    else parsed.max_asset_weight
                ),
            ),
            "max_market_weights": (
                constraints.max_market_weights
                if constraints.max_market_weights
                else parsed.max_market_weights
            ),
            "max_turnover": (
                constraints.max_turnover
                if constraints.max_turnover is not None
                else parsed.max_turnover
            ),
            "allow_new_positions": (
                constraints.allow_new_positions
                if constraints.allow_new_positions is not None
                else parsed.allow_new_positions
            ),
        }
    )


def _risk_layer(
    config: Phase7RunConfig,
    *,
    run_dir: Path,
    registry: AgentRegistry | None,
    tool_registry: ToolRegistry,
) -> RiskLayerResult:
    layer = config.layers.risk
    markets = tuple(str(item) for item in config.market_membership)
    policy = AdministratorRiskPolicy.from_environment(
        config.administrator_environment
    )
    if not layer.enabled:
        merged = merge_risk_directive(
            None,
            policy=policy,
            markets=markets,
            mode="enforced",
        )
        return RiskLayerResult(
            enabled=False,
            due=False,
            source="disabled",
            directive=None,
            merge=merged,
        )
    due = cadence_due(layer.cadence, config.as_of_index)
    team: TeamRunResult | None = None
    if due:
        assert layer.team is not None
        assert config.risk_context is not None
        team = _run_team(
            config,
            layer="risk",
            team=layer.team,
            payload={
                "risk_context": config.risk_context.model_dump(mode="json"),
                "risk_mode": layer.mode,
                "market_membership": list(markets),
            },
            run_dir=run_dir,
            registry=registry,
            tool_registry=tool_registry,
        )
        fallback = static_risk_fallback(markets)
        directive = _risk_from_aggregate(team.aggregate.decision, fallback)
        source: DirectiveSource = "fallback" if directive == fallback else "agent"
    elif layer.previous_directive is not None:
        directive = layer.previous_directive
        source = "previous"
    else:
        directive = static_risk_fallback(markets)
        source = "fallback"
    merged = merge_risk_directive(
        directive,
        policy=policy,
        markets=markets,
        mode=layer.mode,
    )
    return RiskLayerResult(
        enabled=True,
        due=due,
        source=source,
        directive=directive,
        merge=merged,
        team=team,
    )


def _hierarchical_layer(
    config: Phase7RunConfig,
    *,
    run_dir: Path,
    registry: AgentRegistry | None,
    tool_registry: ToolRegistry,
) -> HierarchicalLayerResult:
    layer = config.layers.hierarchical
    if not layer.enabled:
        return HierarchicalLayerResult(
            enabled=False,
            due=False,
            source="disabled",
            directive=None,
        )
    due = cadence_due(layer.cadence, config.as_of_index)
    team: TeamRunResult | None = None
    if due:
        assert layer.team is not None
        team = _run_team(
            config,
            layer="hierarchical",
            team=layer.team,
            payload={
                "regime_features": config.hierarchical_features,
                "market_membership": list(config.market_membership),
                "fusion": layer.fusion,
            },
            run_dir=run_dir,
            registry=registry,
            tool_registry=tool_registry,
        )
        parsed = _payload_model(
            team.aggregate.decision,
            "hierarchical_directive",
            HierarchicalDirective,
        )
        directive = (
            parsed
            if isinstance(parsed, HierarchicalDirective)
            else static_hierarchical_fallback()
        )
        source: DirectiveSource = (
            "fallback"
            if not isinstance(parsed, HierarchicalDirective)
            or (
                team.fallback > 0
                and directive == static_hierarchical_fallback()
            )
            else "agent"
        )
    elif layer.previous_directive is not None:
        directive = layer.previous_directive
        source = "previous"
    else:
        directive = static_hierarchical_fallback()
        source = "fallback"
    return HierarchicalLayerResult(
        enabled=True,
        due=due,
        source=source,
        directive=directive,
        team=team,
    )


def replay_phase7_bundle(bundle_path: Path) -> DirectiveProjection:
    """Recompute hard merge and projection from recorded validated directives only."""
    bundle = Phase7ReplayBundle.model_validate_json(
        bundle_path.read_text(encoding="utf-8")
    )
    policy = AdministratorRiskPolicy.from_environment(bundle.environment)
    risk = merge_risk_directive(
        bundle.risk_proposed,
        policy=policy,
        markets=tuple(str(item) for item in bundle.markets),
        mode=bundle.risk_mode,
    )
    fusion = fuse_constraint_directives(
        environment=bundle.environment,
        markets=bundle.markets,
        risk=risk,
        hierarchical=bundle.hierarchical,
    )
    return project_with_directives(
        bundle.raw_action,
        current_weights=bundle.current_weights,
        tradable_mask=bundle.tradable_mask,
        markets=bundle.markets,
        fusion=fusion,
    )


def execute_phase7_stack(
    config: Phase7RunConfig,
    *,
    registry: AgentRegistry | None = None,
    tool_registry: ToolRegistry | None = None,
) -> Phase7RunSummary:
    """Run enabled layers, intersect hard limits, project once, and verify Replay."""
    workspace = config.workspace_root.resolve()
    output_root = _inside_workspace(config.output_dir, workspace)
    run_dir = output_root / config.run_id
    if run_dir.exists():
        raise FileExistsError(f"Phase 7 run already exists: {run_dir}")
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
    tools = tool_registry or build_builtin_tool_registry(workspace)
    research = _research_layer(
        config,
        run_dir=run_dir,
        registry=registry,
        tool_registry=tools,
    )
    risk = _risk_layer(
        config,
        run_dir=run_dir,
        registry=registry,
        tool_registry=tools,
    )
    hierarchical = _hierarchical_layer(
        config,
        run_dir=run_dir,
        registry=registry,
        tool_registry=tools,
    )
    fusion = fuse_constraint_directives(
        environment=config.administrator_environment,
        markets=config.market_membership,
        risk=risk.merge,
        hierarchical=hierarchical.directive,
    )
    projection = project_with_directives(
        config.raw_action,
        current_weights=config.current_weights,
        tradable_mask=config.tradable_mask,
        markets=config.market_membership,
        fusion=fusion,
    )
    journal = DirectiveJournal(run_dir / "agent" / "directives.jsonl")
    if research.directive is not None:
        journal.append("research", research.directive)
    if risk.directive is not None:
        journal.append("risk_proposed", risk.directive)
    journal.append("risk_effective", risk.merge.effective)
    if hierarchical.directive is not None:
        journal.append("hierarchical", hierarchical.directive)
    journal.append("fusion", fusion)
    journal.append("projection", projection)
    load_directive_journal(journal.path)

    bundle = Phase7ReplayBundle(
        environment=config.administrator_environment,
        markets=config.market_membership,
        raw_action=config.raw_action,
        current_weights=config.current_weights,
        tradable_mask=config.tradable_mask,
        risk_mode=config.layers.risk.mode,
        risk_proposed=risk.directive,
        hierarchical=hierarchical.directive,
        research=research.directive,
    )
    bundle_path = run_dir / "agent" / "directive_replay.json"
    bundle_path.write_text(
        json.dumps(
            bundle.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    replay_verified = (
        replay_phase7_bundle(bundle_path) == projection
        if config.verify_directive_replay
        else False
    )
    teams = tuple(
        item
        for item in (research.team, risk.team, hierarchical.team)
        if item is not None
    )
    summary = Phase7RunSummary(
        run_id=config.run_id,
        preset=config.preset,
        provider_runtimes_started=len(teams),
        network_used=any(item.network_used for item in teams),
        research=research,
        risk=risk,
        hierarchical=hierarchical,
        fusion=fusion,
        projection=projection,
        directive_replay_verified=replay_verified,
    )
    (run_dir / "phase7_summary.json").write_text(
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
    write_run_manifest(
        run_dir,
        workspace_root=workspace,
        run_id=config.run_id,
        kind="phase7",
        config_path=run_dir / "config.resolved.yaml",
        seed=config.seed,
    )
    return summary
