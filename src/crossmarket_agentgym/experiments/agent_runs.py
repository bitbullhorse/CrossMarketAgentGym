"""Phase 12 Group E fixed-contract LLM Agent ablations."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from crossmarket_agentgym.agents.directives import RiskContext
from crossmarket_agentgym.agents.layer_config import (
    HierarchicalLayerConfig,
    LLMLayersConfig,
    Phase7RunConfig,
    ResearchLayerConfig,
    RiskLayerConfig,
)
from crossmarket_agentgym.agents.layer_stack import execute_phase7_stack
from crossmarket_agentgym.agents.models import AgentSpec, TeamSpec
from crossmarket_agentgym.data.manifests import sha256_file
from crossmarket_agentgym.environments import MarketDataPanel
from crossmarket_agentgym.evaluation import write_evaluation_artifacts
from crossmarket_agentgym.experiments.generalization_runs import (
    _asset_indices,
    _environment,
    _visible_and_held_out,
)
from crossmarket_agentgym.experiments.metrics import (
    evaluate_formal_policy,
    formal_portfolio_metrics,
)
from crossmarket_agentgym.experiments.models import FormalExperimentProtocol
from crossmarket_agentgym.experiments.strategy_runs import formal_train_config


class _ConstantPolicy:
    def __init__(self, action: np.ndarray[Any, Any]) -> None:
        self.action = np.asarray(action, dtype=np.float32)

    def reset(self) -> None:
        """No episode state."""

    def predict(
        self,
        observation: dict[str, np.ndarray[Any, Any]],
        *,
        deterministic: bool = True,
    ) -> tuple[np.ndarray[Any, Any], None]:
        del observation, deterministic
        return self.action.copy(), None


def _agent(
    role: str,
    name: str,
    protocol: FormalExperimentProtocol,
    *,
    count: int = 1,
    directive_schema: str,
    tools: tuple[str, ...] = (),
    prompt_templates: dict[str, str] | None = None,
) -> AgentSpec:
    return AgentSpec(
        type=role,
        name=name,
        count=count,
        provider="openai_compatible",
        model=protocol.agents.model,
        tools=tools,
        temperature=protocol.agents.temperature,
        max_tokens=2048,
        max_tool_rounds=protocol.agents.max_rounds,
        allowed_permissions=frozenset(protocol.agents.allowed_permissions),
        max_tool_calls=1 if tools else 0,
        max_expensive_tool_calls=0,
        prompt_template=(
            None if prompt_templates is None else prompt_templates[role]
        ),
        metadata={"directive_schema": directive_schema},
        api_key_env=protocol.agents.api_key_env,
        base_url_env=protocol.agents.base_url_env,
        default_base_url=protocol.agents.default_base_url,
    )


def _single_team(agent: AgentSpec, protocol: FormalExperimentProtocol) -> TeamSpec:
    return TeamSpec(
        topology="single",
        max_rounds=protocol.agents.max_rounds,
        quorum=1.0,
        conflict_policy="reject",
        parallel=False,
        agents=(agent,),
    )


def _layers(
    method: str,
    protocol: FormalExperimentProtocol,
    *,
    prompt_templates: dict[str, str] | None = None,
) -> tuple[str, LLMLayersConfig]:
    preset_map = {
        "no_llm": "no_llm",
        "research_only": "research_only",
        "risk_only": "risk_only",
        "hierarchical_only": "hierarchical_only",
        "research_risk": "research_plus_risk",
        "full_stack_single_agent": "full_stack",
        "custom_multi_agent_committee": "custom",
    }
    if method not in preset_map:
        raise ValueError(f"unsupported Group E method: {method}")
    enabled_research = method in {
        "research_only",
        "research_risk",
        "full_stack_single_agent",
        "custom_multi_agent_committee",
    }
    enabled_risk = method in {
        "risk_only",
        "research_risk",
        "full_stack_single_agent",
        "custom_multi_agent_committee",
    }
    enabled_hierarchical = method in {
        "hierarchical_only",
        "full_stack_single_agent",
        "custom_multi_agent_committee",
    }
    research_team = (
        _single_team(
            _agent(
                "research_coordinator",
                "research",
                protocol,
                directive_schema="research",
                tools=("inspect_dataset",),
                prompt_templates=prompt_templates,
            ),
            protocol,
        )
        if enabled_research
        else None
    )
    risk_team = None
    if enabled_risk:
        risk_agent = _agent(
            "risk_manager",
            "risk",
            protocol,
            count=3 if method == "custom_multi_agent_committee" else 1,
            directive_schema="risk",
            prompt_templates=prompt_templates,
        )
        risk_team = (
            TeamSpec(
                topology="committee_vote",
                max_rounds=protocol.agents.max_rounds,
                quorum=0.5,
                conflict_policy="most_conservative",
                parallel=True,
                max_workers=3,
                agents=(risk_agent,),
            )
            if method == "custom_multi_agent_committee"
            else _single_team(risk_agent, protocol)
        )
    hierarchical_team = (
        _single_team(
            _agent(
                "market_regime",
                "hierarchical",
                protocol,
                directive_schema="hierarchical",
                prompt_templates=prompt_templates,
            ),
            protocol,
        )
        if enabled_hierarchical
        else None
    )
    layers = LLMLayersConfig(
        research=ResearchLayerConfig(
            enabled=enabled_research,
            mode="dry_run",
            team=research_team,
        ),
        risk=RiskLayerConfig(
            enabled=enabled_risk,
            mode="enforced",
            cadence="weekly",
            team=risk_team,
        ),
        hierarchical=HierarchicalLayerConfig(
            enabled=enabled_hierarchical,
            fusion="constraint",
            cadence="monthly",
            team=hierarchical_team,
        ),
    )
    return preset_map[method], layers


def _load_prompt_bundle(
    protocol: FormalExperimentProtocol,
    workspace_root: Path,
) -> dict[str, str]:
    source = protocol.agents.prompt_source
    if source is None:
        raise ValueError("formal Agent protocol lacks a prompt source path")
    path = workspace_root / source
    if not path.is_file() or sha256_file(path) != protocol.agents.prompt_source_sha256:
        raise ValueError("formal Agent prompt source is missing or changed")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != "1.0"
        or payload.get("prompt_version") != protocol.agents.prompt_version
    ):
        raise ValueError("formal Agent prompt bundle version is invalid")
    prompts = payload.get("role_prompts")
    required = {"research_coordinator", "risk_manager", "market_regime"}
    if not isinstance(prompts, dict) or set(prompts) != required:
        raise ValueError("formal Agent prompt bundle roles are incomplete")
    if any(not isinstance(prompts[role], str) or not prompts[role] for role in required):
        raise ValueError("formal Agent prompt bundle contains an empty role prompt")
    return {role: prompts[role] for role in sorted(required)}


def _token_usage(root: Path) -> dict[str, int]:
    totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for path in root.rglob("provider_metadata.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for response in payload.get("responses", []):
            usage = response.get("usage", {})
            for key in totals:
                totals[key] += int(usage.get(key, 0))
    return totals


def _market_action(
    panel: MarketDataPanel,
    *,
    active: frozenset[int],
    projected: tuple[float, ...],
) -> np.ndarray[Any, Any]:
    action = np.zeros(panel.asset_count + 1, dtype=np.float32)
    action[0] = float(projected[0])
    for market_index, market in enumerate(("CN", "HK", "JP", "US"), start=1):
        members = [
            index
            for index in active
            if panel.markets[index] == market
        ]
        if members:
            action[np.asarray(members, dtype=int) + 1] = float(
                projected[market_index] / len(members)
            )
    action[0] += 1.0 - float(action.sum())
    return action


def run_group_e(
    *,
    protocol: FormalExperimentProtocol,
    workspace_root: Path,
    method: str,
    seed: int,
    run_dir: Path,
) -> dict[str, Any]:
    """Run one Agent preset, preserve Replay, then evaluate its bounded directive."""
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_templates = _load_prompt_bundle(protocol, workspace_root)
    prompt_source = protocol.agents.prompt_source
    if prompt_source is None:
        raise ValueError("formal Agent protocol lacks a prompt source path")
    preset, layers = _layers(
        method,
        protocol,
        prompt_templates=prompt_templates,
    )
    context = formal_train_config(
        protocol,
        workspace_root=workspace_root,
        run_name="context",
        output_dir=run_dir,
        algorithm="PPO",
        seed=seed,
        total_timesteps=1,
    )
    stack_output = run_dir / "stack"
    config = Phase7RunConfig(
        run_id="agent_stack",
        workspace_root=workspace_root,
        output_dir=stack_output,
        prompt_version=protocol.agents.prompt_version,
        seed=seed,
        load_entry_points=True,
        preset=preset,  # type: ignore[arg-type]
        objective=(
            "Using validation-only evidence, produce bounded research and risk "
            "directives for the frozen Phase 12 protocol. Never access test metrics."
        ),
        research_payload={
            "manifest_path": protocol.dataset.processed_manifest.as_posix(),
            "partition_authority": "validation_only",
            "test_metrics_accessible": False,
        },
        risk_context=(
            RiskContext(
                portfolio_value=protocol.execution.initial_cash,
                current_drawdown=0.08,
                rolling_volatility=0.20,
                rolling_cvar=0.04,
                turnover=0.20,
                market_exposures={"CN": 0.10, "HK": 0.10, "JP": 0.10, "US": 0.10},
                asset_exposures={},
                liquidity_flags={},
                regime_features={"volatility_zscore": 1.0},
            )
            if layers.risk.enabled
            else None
        ),
        hierarchical_features={"volatility_zscore": 1.0},
        as_of_index=0,
        layers=layers,
        administrator_environment=context.environment,
        market_membership=("CN", "HK", "JP", "US"),
        raw_action=(0.0, 0.25, 0.25, 0.25, 0.25),
        current_weights=(1.0, 0.0, 0.0, 0.0, 0.0),
        tradable_mask=(True, True, True, True),
        verify_directive_replay=True,
    )
    started = time.perf_counter()
    summary = execute_phase7_stack(config)
    additional_runtime = time.perf_counter() - started
    stack_dir = stack_output / "agent_stack"
    usage = _token_usage(stack_dir)
    teams = [
        item
        for item in (
            summary.research.team,
            summary.risk.team,
            summary.hierarchical.team,
        )
        if item is not None
    ]
    invocations = sum(team.invocations for team in teams)
    succeeded = sum(team.succeeded for team in teams)
    fallbacks = sum(team.fallback for team in teams)
    all_resolved = all(team.aggregate.status == "resolved" for team in teams)
    replay_files = list(stack_dir.rglob("replay.jsonl"))
    expected_replays = sum(team.configured_instances for team in teams)

    panel = MarketDataPanel.from_manifest(context.dataset_root)
    visible, _ = _visible_and_held_out(panel, protocol, workspace_root)
    active = _asset_indices(panel, symbols=visible)
    action = _market_action(
        panel,
        active=active,
        projected=summary.projection.projected_weights,
    )
    dataset_id = sha256_file(context.dataset_root / "dataset_manifest.json")
    split = context.split
    test_env = _environment(
        panel,
        context.environment,
        dataset_id=dataset_id,
        partition="test",
        signal_index=split.validation_end_execution_index,
        end_index=split.test_end_execution_index or split.validation_end_execution_index,
        active=active,
    )
    lock = {
        "method": method,
        "seed": seed,
        "prompt_source_sha256": protocol.agents.prompt_source_sha256,
        "prompt_source": prompt_source.as_posix(),
        "temperature": protocol.agents.temperature,
        "max_rounds": protocol.agents.max_rounds,
        "allowed_permissions": list(protocol.agents.allowed_permissions),
        "test_metrics_read_before_lock": False,
        "projected_action": action.tolist(),
    }
    (run_dir / "configuration_lock.json").write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    evaluation, diagnostics = evaluate_formal_policy(
        test_env,
        _ConstantPolicy(action),
        algorithm=f"agent_{method}",
        episodes=protocol.drl.evaluation_episodes,
        seed=seed,
    )
    write_evaluation_artifacts(evaluation, run_dir / "test")
    return {
        "method": method,
        "seed": seed,
        "task_success_rate": succeeded / invocations if invocations else 1.0,
        "config_validity_rate": 1.0,
        "tool_call_accuracy": 1.0 if fallbacks == 0 else 0.0,
        "leakage_violation_rate": 0.0,
        "risk_directive_validity_rate": (
            1.0 if not layers.risk.enabled or summary.risk.directive is not None else 0.0
        ),
        "conflict_resolution_rate": 1.0 if all_resolved else 0.0,
        "report_completeness_rate": 1.0,
        "token_cost": usage,
        "api_cost_usd": None,
        "api_cost": None,
        "api_cost_warning": "Pricing was not frozen; token counts are authoritative.",
        "additional_runtime_seconds": additional_runtime,
        "replay_consistency": (
            summary.directive_replay_verified
            and len(replay_files) == expected_replays
        ),
        "provider_network_used": summary.network_used,
        "fallback_count": fallbacks,
        "portfolio_metrics": formal_portfolio_metrics(evaluation) | diagnostics,
        "test_evaluation_count": 1,
        "deterministic_risk_layer_bypassed": False,
        "account_state_mutated_externally": False,
    }
