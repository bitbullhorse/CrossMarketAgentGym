"""Provider-backed built-in role implementations for Phase 6."""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

from crossmarket_agentgym.agents.directives import (
    HierarchicalDirective,
    ResearchDirective,
    ResearchMode,
    RiskDirective,
    static_hierarchical_fallback,
    static_research_fallback,
    static_risk_fallback,
)
from crossmarket_agentgym.agents.models import (
    AgentContext,
    AgentDecision,
    AgentInstance,
    DecisionConstraints,
    DecisionKind,
    RoleInvocation,
)
from crossmarket_agentgym.agents.providers import Message, ReplayJournal, create_provider
from crossmarket_agentgym.agents.roles.base import RoleServices
from crossmarket_agentgym.agents.session import ProviderToolSession, SessionOutcome
from crossmarket_agentgym.agents.tools import ToolExecutor, ToolPolicy
from crossmarket_agentgym.audit.agent import AgentAuditWriter

DirectiveT = TypeVar("DirectiveT", bound=BaseModel)

_ROLE_PROMPTS: dict[str, str] = {
    "research_coordinator": (
        "You are the Research Orchestration Agent. Return only the requested structured "
        "decision. Coordinate research tasks, but never claim validation as test evidence, "
        "alter market data, or start work outside the configured tool budget."
    ),
    "data_quality": (
        "Review only structured data-quality evidence. Do not invent observations or alter data."
    ),
    "experiment_designer": (
        "Design a reproducible experiment using only the supplied evidence and capabilities."
    ),
    "environment_reviewer": (
        "Review environment correctness, information timing, and accounting evidence."
    ),
    "training": (
        "Review a bounded training task. Never read test metrics or exceed configured budgets."
    ),
    "hyperparameter_tuning": (
        "Review validation-only tuning evidence. The test partition is unavailable for tuning."
    ),
    "market_regime": (
        "You are the Hierarchical Strategy Agent. Produce low-frequency structured advice only. "
        "You cannot set account state or bypass deterministic portfolio projection."
    ),
    "risk_manager": (
        "You are the Risk Management Agent. Produce structured conservative limits only. "
        "You cannot relax administrator hard limits, mutate account state, or place orders."
    ),
    "portfolio_reviewer": (
        "Review the structured portfolio proposal without mutating account or execution state."
    ),
    "backtest_auditor": (
        "Audit partition, execution, and accounting evidence. Never treat validation as test."
    ),
    "report_writer": (
        "Summarize supplied structured evidence without inventing metrics or modifying artifacts."
    ),
    "judge": (
        "Resolve only the supplied structured candidate decisions. Prefer safety under ambiguity."
    ),
}


def _static_fallback(role_type: str) -> AgentDecision:
    if role_type == "risk_manager":
        return AgentDecision(
            decision="reject",
            summary="Static risk fallback denies new exposure.",
            confidence=1.0,
            risk_score=1.0,
            constraints=DecisionConstraints(
                cash_floor=1.0,
                max_asset_weight=0.0,
                max_turnover=0.0,
                allow_new_positions=False,
            ),
        )
    if role_type == "market_regime":
        return AgentDecision(
            decision="revise",
            summary="Static hierarchical fallback requests deterministic safe limits.",
            confidence=0.0,
            risk_score=1.0,
            constraints=DecisionConstraints(
                cash_floor=1.0,
                max_asset_weight=0.0,
                max_turnover=0.0,
                allow_new_positions=False,
            ),
        )
    return AgentDecision(
        decision="abstain",
        summary="Static role fallback provides no authority to continue.",
        confidence=0.0,
        risk_score=1.0,
    )


class ProviderRoleAgent:
    """Stateful Provider/tool session shared by all built-in role types."""

    def __init__(self, instance: AgentInstance, services: RoleServices) -> None:
        self.instance = instance
        self.services = services
        spec = instance.spec
        provider_config = spec.provider_config(instance.instance_id, instance.seed)
        self.provider = create_provider(
            provider_config,
            mock_script=spec.mock_script(instance.index),
        )
        allowed_tools = frozenset(spec.tools) if spec.tools else None
        self.tool_executor = ToolExecutor(
            services.tool_registry,
            ToolPolicy(
                allowed_permissions=spec.allowed_permissions,
                allowed_tools=allowed_tools,
                max_total_calls=spec.max_tool_calls if spec.tools else 0,
                max_expensive_calls=spec.max_expensive_tool_calls,
                max_cumulative_seconds=spec.max_tool_seconds,
                require_budget_before_expensive=(
                    spec.require_budget_before_expensive
                ),
            ),
            services.workspace_root,
        )
        instance_run_dir = services.run_dir / "agent_instances" / instance.instance_id
        self.audit = AgentAuditWriter(
            instance_run_dir,
            provider_config=provider_config.model_dump(mode="json"),
            prompt_version=services.prompt_version,
        )
        replay_path = instance_run_dir / "agent" / "replay.jsonl"
        self.replay_journal = (
            None if spec.provider == "replay" else ReplayJournal(replay_path)
        )

    def _messages(self, context: AgentContext) -> list[Message]:
        role_prompt = self.instance.spec.prompt_template or _ROLE_PROMPTS.get(
            self.instance.spec.type,
            (
                "Return only the requested structured AgentDecision. You have no authority "
                "to mutate account state, execute shell text, or bypass configured tools."
            ),
        )
        context_payload = {
            "instance_id": self.instance.instance_id,
            "objective": context.objective,
            "payload": context.payload,
            "round_index": context.round_index,
            "upstream": [
                item.model_dump(mode="json") for item in context.upstream
            ],
        }
        return [
            Message(role="system", content=role_prompt),
            Message(
                role="user",
                content=json.dumps(
                    context_payload,
                    allow_nan=False,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            ),
        ]

    def run(self, context: AgentContext) -> RoleInvocation:
        """Execute one bounded invocation through the shared Phase 5 session."""
        spec = self.instance.spec
        fallback = spec.fallback or _static_fallback(spec.type)
        outcome = self._run_session(
            context,
            response_schema=AgentDecision,
            fallback=fallback,
        )
        return RoleInvocation(
            decision=outcome.value,
            used_fallback=outcome.used_fallback,
            error_code=outcome.error_code,
        )

    def _run_session(
        self,
        context: AgentContext,
        *,
        response_schema: type[DirectiveT],
        fallback: DirectiveT,
    ) -> SessionOutcome[DirectiveT]:
        """Run one typed domain or generic schema through identical safety controls."""
        spec = self.instance.spec
        invocation_seed = (self.instance.seed + context.round_index - 1) % (2**32)
        return ProviderToolSession(
            provider=self.provider,
            tool_executor=self.tool_executor,
            audit=self.audit,
            replay_journal=self.replay_journal,
            max_rounds=spec.max_tool_rounds,
        ).run(
            self._messages(context),
            response_schema=response_schema,
            fallback=fallback,
            generation_config=spec.generation_config(invocation_seed),
            tool_names=list(spec.tools),
        )

    def close(self) -> None:
        """Close a network Provider when it exposes a close method."""
        close = getattr(self.provider, "close", None)
        if callable(close):
            close()


class ResearchOrchestrationAgent(ProviderRoleAgent):
    """First-layer typed research planner and bounded tool orchestrator."""

    def run(self, context: AgentContext) -> RoleInvocation:
        if self.instance.spec.metadata.get("directive_schema") != "research":
            return super().run(context)
        raw_mode = context.payload.get("research_mode", "plan_only")
        mode: ResearchMode = (
            raw_mode
            if raw_mode in {"plan_only", "dry_run", "execute"}
            else "plan_only"
        )
        fallback = static_research_fallback(mode, context.objective)
        outcome = self._run_session(
            context,
            response_schema=ResearchDirective,
            fallback=fallback,
        )
        directive = outcome.value
        used_fallback = outcome.used_fallback
        error_code = outcome.error_code
        if directive.mode != mode:
            directive = fallback
            used_fallback = True
            error_code = "research_mode_mismatch"
            self.audit.record_fallback(
                error_code,
                "research directive mode did not match administrator configuration",
            )
        decision_kind: DecisionKind = (
            "approve"
            if directive.steps
            else ("reject" if directive.safe_to_execute else "abstain")
        )
        return RoleInvocation(
            decision=AgentDecision(
                decision=decision_kind,
                summary=directive.rationale,
                confidence=directive.confidence,
                risk_score=0.0,
                payload={
                    "research_directive": directive.model_dump(mode="json")
                },
            ),
            used_fallback=used_fallback,
            error_code=error_code,
        )


class RiskManagementAgent(ProviderRoleAgent):
    """Second-layer typed risk proposal; hard-policy merge remains external."""

    def run(self, context: AgentContext) -> RoleInvocation:
        if self.instance.spec.metadata.get("directive_schema") != "risk":
            return super().run(context)
        markets_raw = context.payload.get("market_membership", ())
        markets = tuple(
            str(item)
            for item in markets_raw
            if isinstance(item, str)
        ) if isinstance(markets_raw, list | tuple) else ()
        fallback = static_risk_fallback(markets)
        outcome = self._run_session(
            context,
            response_schema=RiskDirective,
            fallback=fallback,
        )
        directive = outcome.value
        if not directive.allow_new_positions and directive.risk_budget == 0.0:
            decision_kind: DecisionKind = "reject"
        elif (
            directive.risk_budget < 1.0
            or directive.cash_floor > 0.0
            or not directive.allow_new_positions
        ):
            decision_kind = "revise"
        else:
            decision_kind = "approve"
        return RoleInvocation(
            decision=AgentDecision(
                decision=decision_kind,
                summary=directive.rationale,
                confidence=directive.confidence,
                risk_score=1.0 - directive.risk_budget,
                constraints=DecisionConstraints(
                    cash_floor=directive.cash_floor,
                    max_asset_weight=directive.max_asset_weight,
                    max_market_weights=directive.max_market_weights,
                    max_turnover=directive.max_turnover,
                    allow_new_positions=directive.allow_new_positions,
                ),
                payload={"risk_directive": directive.model_dump(mode="json")},
            ),
            used_fallback=outcome.used_fallback,
            error_code=outcome.error_code,
        )


class HierarchicalStrategyAgent(ProviderRoleAgent):
    """Third-layer typed low-frequency constraint directive."""

    def run(self, context: AgentContext) -> RoleInvocation:
        if self.instance.spec.metadata.get("directive_schema") != "hierarchical":
            return super().run(context)
        fallback = static_hierarchical_fallback()
        outcome = self._run_session(
            context,
            response_schema=HierarchicalDirective,
            fallback=fallback,
        )
        directive = outcome.value
        decision_kind: DecisionKind = (
            "approve"
            if directive.market_regime in {"risk_on", "neutral"}
            else (
                "abstain"
                if directive.market_regime == "unknown"
                else "revise"
            )
        )
        return RoleInvocation(
            decision=AgentDecision(
                decision=decision_kind,
                summary=(
                    "Hierarchical regime "
                    f"{directive.market_regime} with risk budget "
                    f"{directive.global_risk_budget:.6f}."
                ),
                confidence=directive.confidence,
                risk_score=1.0 - directive.global_risk_budget,
                constraints=DecisionConstraints(
                    cash_floor=1.0 - directive.global_risk_budget,
                    max_market_weights=directive.market_budgets,
                    allow_new_positions=directive.global_risk_budget > 0.0,
                ),
                payload={
                    "hierarchical_directive": directive.model_dump(mode="json")
                },
            ),
            used_fallback=outcome.used_fallback,
            error_code=outcome.error_code,
        )


def provider_role_factory(
    instance: AgentInstance,
    services: RoleServices,
) -> ProviderRoleAgent:
    """Construct the appropriate built-in role while preserving one runtime contract."""
    role_class: type[ProviderRoleAgent]
    if instance.spec.type == "research_coordinator":
        role_class = ResearchOrchestrationAgent
    elif instance.spec.type == "risk_manager":
        role_class = RiskManagementAgent
    elif instance.spec.type == "market_regime":
        role_class = HierarchicalStrategyAgent
    else:
        role_class = ProviderRoleAgent
    return role_class(instance, services)


BUILTIN_ROLE_TYPES = (
    "research_coordinator",
    "data_quality",
    "experiment_designer",
    "environment_reviewer",
    "training",
    "hyperparameter_tuning",
    "market_regime",
    "risk_manager",
    "portfolio_reviewer",
    "backtest_auditor",
    "report_writer",
    "judge",
    "custom",
)
