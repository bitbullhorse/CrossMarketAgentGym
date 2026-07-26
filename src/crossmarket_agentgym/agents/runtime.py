"""Unified single-Agent and multi-Agent execution runtime."""

from __future__ import annotations

import hashlib
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from pathlib import Path
from time import perf_counter

from crossmarket_agentgym.agents.aggregation import aggregate_results
from crossmarket_agentgym.agents.models import (
    AgentContext,
    AgentExecutionResult,
    AgentInstance,
    AgentRuntimeConfig,
    AgentStatus,
    TeamRunResult,
    UpstreamDecision,
)
from crossmarket_agentgym.agents.roles import (
    AgentRegistry,
    RoleServices,
    RuntimeRole,
)
from crossmarket_agentgym.agents.tools import ToolRegistry, build_builtin_tool_registry
from crossmarket_agentgym.audit.logging import redact_secrets
from crossmarket_agentgym.audit.runtime import RuntimeAuditWriter


def _instance_seed(base_seed: int, name: str, index: int) -> int:
    digest = hashlib.sha256(f"{base_seed}:{name}:{index}".encode()).digest()
    return int.from_bytes(digest[:4], byteorder="big")


def expand_agent_specs(config: AgentRuntimeConfig) -> tuple[AgentInstance, ...]:
    """Expand enabled specs in configuration order with stable IDs and seeds."""
    instances: list[AgentInstance] = []
    for spec in config.team.agents:
        if not spec.enabled:
            continue
        for index in range(spec.count):
            instance_id = spec.name if spec.count == 1 else f"{spec.name}_{index}"
            instances.append(
                AgentInstance(
                    instance_id=instance_id,
                    index=index,
                    seed=_instance_seed(config.seed, spec.name, index),
                    spec=spec,
                )
            )
    return tuple(instances)


class AgentRuntime:
    """Execute all supported topologies through the same role and result contract."""

    def __init__(
        self,
        config: AgentRuntimeConfig,
        *,
        run_dir: Path,
        registry: AgentRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.config = config
        self.run_dir = run_dir
        self.instances = expand_agent_specs(config)
        self.registry = registry or AgentRegistry()
        if config.load_entry_points:
            self.registry.load_entry_points()
        available = set(self.registry.registered_types())
        unknown = sorted(
            {item.spec.type for item in self.instances if item.spec.type not in available}
        )
        if unknown:
            raise KeyError(f"unknown Agent roles: {', '.join(unknown)}")
        services = RoleServices(
            workspace_root=config.workspace_root.resolve(),
            run_dir=run_dir,
            prompt_version=config.prompt_version,
            tool_registry=tool_registry
            or build_builtin_tool_registry(config.workspace_root.resolve()),
        )
        self.roles: dict[str, RuntimeRole] = {
            item.instance_id: self.registry.create(item, services)
            for item in self.instances
        }
        self._invocation_counts: dict[str, int] = {
            item.instance_id: 0 for item in self.instances
        }
        self.audit = RuntimeAuditWriter(run_dir)
        self.audit.record_team(config.team, self.instances)

    def _invoke(
        self,
        instance: AgentInstance,
        context: AgentContext,
        invocation_id: str,
    ) -> AgentExecutionResult:
        started = perf_counter()
        attempts = 0
        for attempts in range(1, instance.spec.max_retries + 2):
            try:
                outcome = self.roles[instance.instance_id].run(context)
                status: AgentStatus = (
                    "fallback" if outcome.used_fallback else "succeeded"
                )
                return AgentExecutionResult(
                    invocation_id=invocation_id,
                    instance_id=instance.instance_id,
                    role_type=instance.spec.type,
                    base_name=instance.spec.name,
                    seed=instance.seed,
                    round_index=context.round_index,
                    weight=instance.spec.weight,
                    status=status,
                    attempts=attempts,
                    duration_seconds=perf_counter() - started,
                    decision=outcome.decision,
                    error_code=outcome.error_code,
                )
            except Exception as error:
                if attempts <= instance.spec.max_retries:
                    continue
                return AgentExecutionResult(
                    invocation_id=invocation_id,
                    instance_id=instance.instance_id,
                    role_type=instance.spec.type,
                    base_name=instance.spec.name,
                    seed=instance.seed,
                    round_index=context.round_index,
                    weight=instance.spec.weight,
                    status="failed",
                    attempts=attempts,
                    duration_seconds=perf_counter() - started,
                    error_code="role_execution_failed",
                    error_message=redact_secrets(
                        f"{error.__class__.__name__}: {error}"
                    ),
                )
        raise AssertionError("unreachable Agent retry state")

    def _next_invocation_id(
        self,
        instance: AgentInstance,
        round_index: int,
    ) -> str:
        self._invocation_counts[instance.instance_id] += 1
        return (
            f"{instance.instance_id}.r{round_index}."
            f"i{self._invocation_counts[instance.instance_id]}"
        )

    def _timeout_result(
        self,
        instance: AgentInstance,
        context: AgentContext,
        invocation_id: str,
    ) -> AgentExecutionResult:
        return AgentExecutionResult(
            invocation_id=invocation_id,
            instance_id=instance.instance_id,
            role_type=instance.spec.type,
            base_name=instance.spec.name,
            seed=instance.seed,
            round_index=context.round_index,
            weight=instance.spec.weight,
            status="timed_out",
            attempts=1,
            duration_seconds=instance.spec.timeout_seconds,
            error_code="agent_timeout",
            error_message="Agent invocation exceeded its configured timeout.",
        )

    def _batch(
        self,
        instances: tuple[AgentInstance, ...],
        *,
        objective: str,
        payload: dict[str, object],
        round_index: int,
        upstream: tuple[UpstreamDecision, ...],
        parallel: bool | None = None,
    ) -> list[AgentExecutionResult]:
        if not instances:
            return []
        use_parallel = self.config.team.parallel if parallel is None else parallel
        workers = (
            min(self.config.team.max_workers, len(instances))
            if use_parallel
            else 1
        )
        executor = ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="cmag-agent",
        )
        futures: list[
            tuple[
                AgentInstance,
                AgentContext,
                str,
                Future[AgentExecutionResult],
            ]
        ] = []
        results: list[AgentExecutionResult] = []
        try:
            for instance in instances:
                context = AgentContext(
                    run_id=self.config.run_id,
                    objective=objective,
                    payload=payload,
                    round_index=round_index,
                    upstream=upstream,
                )
                invocation_id = self._next_invocation_id(instance, round_index)
                future = executor.submit(
                    self._invoke,
                    instance,
                    context,
                    invocation_id,
                )
                futures.append((instance, context, invocation_id, future))
                if not use_parallel:
                    try:
                        result = future.result(timeout=instance.spec.timeout_seconds)
                    except TimeoutError:
                        future.cancel()
                        result = self._timeout_result(
                            instance,
                            context,
                            invocation_id,
                        )
                    results.append(result)
                    self.audit.record_result(result)
            if use_parallel:
                for instance, context, invocation_id, future in futures:
                    try:
                        result = future.result(timeout=instance.spec.timeout_seconds)
                    except TimeoutError:
                        future.cancel()
                        result = self._timeout_result(
                            instance,
                            context,
                            invocation_id,
                        )
                    results.append(result)
                    self.audit.record_result(result)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return results

    def _instance_named(self, name: str) -> AgentInstance:
        matches = [item for item in self.instances if item.spec.name == name]
        if len(matches) != 1:
            raise ValueError(f"role reference does not resolve uniquely: {name}")
        return matches[0]

    @staticmethod
    def _upstream(
        results: list[AgentExecutionResult],
    ) -> tuple[UpstreamDecision, ...]:
        return tuple(item.upstream() for item in results)

    def _execute_topology(
        self,
    ) -> tuple[list[AgentExecutionResult], int]:
        team = self.config.team
        objective = self.config.objective
        payload: dict[str, object] = dict(self.config.payload)
        all_results: list[AgentExecutionResult] = []
        rounds = 1

        if team.topology in {"single", "committee_vote"}:
            all_results.extend(
                self._batch(
                    self.instances,
                    objective=objective,
                    payload=payload,
                    round_index=1,
                    upstream=(),
                )
            )
        elif team.topology == "pipeline":
            upstream: list[AgentExecutionResult] = []
            for instance in self.instances:
                stage = self._batch(
                    (instance,),
                    objective=objective,
                    payload=payload,
                    round_index=1,
                    upstream=self._upstream(upstream),
                    parallel=False,
                )
                upstream.extend(stage)
                all_results.extend(stage)
        elif team.topology == "supervisor_worker":
            first = self._batch(
                self.instances,
                objective=objective,
                payload=payload,
                round_index=1,
                upstream=(),
            )
            all_results.extend(first)
            if team.max_rounds >= 2:
                supervisor = self._instance_named(team.supervisor or "")
                synthesis = self._batch(
                    (supervisor,),
                    objective=objective,
                    payload=payload,
                    round_index=2,
                    upstream=self._upstream(first),
                    parallel=False,
                )
                all_results.extend(synthesis)
                rounds = 2
        elif team.topology == "debate_then_judge":
            judge = self._instance_named(team.judge or "")
            debaters = tuple(item for item in self.instances if item != judge)
            previous: list[AgentExecutionResult] = []
            for round_index in range(1, team.max_rounds):
                previous = self._batch(
                    debaters,
                    objective=objective,
                    payload=payload,
                    round_index=round_index,
                    upstream=self._upstream(previous),
                )
                all_results.extend(previous)
            judgment = self._batch(
                (judge,),
                objective=objective,
                payload=payload,
                round_index=team.max_rounds,
                upstream=self._upstream(previous),
                parallel=False,
            )
            all_results.extend(judgment)
            rounds = team.max_rounds
        else:
            reducer = self._instance_named(team.supervisor or "")
            mappers = tuple(item for item in self.instances if item != reducer)
            mapped = self._batch(
                mappers,
                objective=objective,
                payload=payload,
                round_index=1,
                upstream=(),
            )
            all_results.extend(mapped)
            reduced = self._batch(
                (reducer,),
                objective=objective,
                payload=payload,
                round_index=2,
                upstream=self._upstream(mapped),
                parallel=False,
            )
            all_results.extend(reduced)
            rounds = 2
        return all_results, rounds

    def run(self) -> TeamRunResult:
        """Run one configured topology and persist its terminal aggregate."""
        results, rounds = self._execute_topology()
        judge_instance = (
            self._instance_named(self.config.team.judge).instance_id
            if self.config.team.judge is not None
            else None
        )
        aggregate = aggregate_results(
            results,
            policy=self.config.team.conflict_policy,
            quorum=self.config.team.quorum,
            expected_instances=(item.instance_id for item in self.instances),
            judge_instance=judge_instance,
        )
        statuses = [item.status for item in results]
        summary = TeamRunResult(
            run_id=self.config.run_id,
            topology=self.config.team.topology,
            configured_instances=len(self.instances),
            invocations=len(results),
            succeeded=statuses.count("succeeded"),
            fallback=statuses.count("fallback"),
            failed=statuses.count("failed"),
            timed_out=statuses.count("timed_out"),
            rounds=rounds,
            parallel=self.config.team.parallel,
            network_used=any(
                item.spec.provider == "openai_compatible" for item in self.instances
            ),
            results=tuple(results),
            aggregate=aggregate,
        )
        self.audit.record_summary(summary)
        return summary

    def close(self) -> None:
        """Release every independent role without suppressing close failures."""
        for instance_id in sorted(self.roles):
            self.roles[instance_id].close()
