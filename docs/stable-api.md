# Stable Python API catalog

Generated from reviewed `__all__` exports for v1.0.0-rc1. Schemas carry field-level constraints.

## `crossmarket_agentgym.__version__`

str(object='') -> str

```text
constant_or_type_alias
```

## `crossmarket_agentgym.agents.AdministratorRiskPolicy`

Immutable absolute risk limits owned outside every LLM.

```text
(*, max_risk_budget: float = 1.0, max_asset_weight: float, default_max_market_weight: float, max_market_weights: dict[str, float] = <factory>, minimum_cash_floor: float, max_turnover: float, allow_new_positions: bool = True, minimum_rebalance_interval: Literal['daily', 'weekly', 'monthly'] = 'daily')
```

## `crossmarket_agentgym.agents.AgentContext`

Immutable input to one role invocation.

```text
(*, run_id: str, objective: str, payload: dict[str, Any] = <factory>, round_index: int, upstream: tuple[crossmarket_agentgym.agents.models.UpstreamDecision, ...] = ())
```

## `crossmarket_agentgym.agents.AgentDecision`

Provider-neutral structured envelope used by every Phase 6 role.

```text
(*, decision: Literal['approve', 'revise', 'reject', 'abstain'], summary: str, confidence: float = 0.0, risk_score: float = 1.0, constraints: crossmarket_agentgym.agents.models.DecisionConstraints = <factory>, payload: dict[str, Any] = <factory>)
```

## `crossmarket_agentgym.agents.AgentExecutionResult`

Auditable outcome of one invocation, including partial failures.

```text
(*, invocation_id: str, instance_id: str, role_type: str, base_name: str, seed: int, round_index: int, weight: float, status: Literal['succeeded', 'fallback', 'failed', 'timed_out'], attempts: int, duration_seconds: float, decision: crossmarket_agentgym.agents.models.AgentDecision | None = None, error_code: str | None = None, error_message: str | None = None)
```

## `crossmarket_agentgym.agents.AgentInstance`

One expanded Agent with independent identity, seed, state, and limits.

```text
(*, instance_id: str, index: int, seed: int, spec: crossmarket_agentgym.agents.models.AgentSpec)
```

## `crossmarket_agentgym.agents.AgentRuntime`

Execute all supported topologies through the same role and result contract.

```text
(config: 'AgentRuntimeConfig', *, run_dir: 'Path', registry: 'AgentRegistry | None' = None, tool_registry: 'ToolRegistry | None' = None) -> 'None'
```

## `crossmarket_agentgym.agents.AgentRuntimeConfig`

Complete credential-free Phase 6 CLI configuration.

```text
(*, run_id: str = 'phase6-runtime-offline', workspace_root: pathlib.Path = '.', output_dir: pathlib.Path = 'runs', prompt_version: str = 'phase6.v1', seed: int = 1024, objective: str, payload: dict[str, Any] = <factory>, load_entry_points: bool = True, team: crossmarket_agentgym.agents.models.TeamSpec)
```

## `crossmarket_agentgym.agents.AgentSpec`

One configurable Agent role, expanded into ``count`` independent instances.

```text
(*, type: str, name: str, count: int = 1, provider: Literal['openai_compatible', 'mock', 'replay'] = 'openai_compatible', model: str = 'deepseek-v4-pro', prompt_template: str | None = None, tools: tuple[str, ...] = (), weight: float = 1.0, temperature: float = 0.0, max_tokens: int = 2048, timeout_seconds: float = 120.0, max_retries: int = 2, retry_backoff_seconds: float = 0.25, max_tool_rounds: int = 3, enabled: bool = True, metadata: dict[str, Any] = <factory>, fallback: crossmarket_agentgym.agents.models.AgentDecision | None = None, allowed_permissions: frozenset[Literal['read', 'compute', 'write', 'expensive']] = frozenset({'compute', 'read'}), max_tool_calls: int = 20, max_expensive_tool_calls: int = 0, max_tool_seconds: float = 300.0, require_budget_before_expensive: bool = True, api_key_env: str = 'DEEPSEEK_API_KEY', base_url_env: str = 'DEEPSEEK_BASE_URL', default_base_url: str = 'https://api.deepseek.com', endpoint: str = '/chat/completions', structured_output_mode: Literal['json_object', 'json_schema'] = 'json_object', replay_path: str | None = None, mock_scripts: tuple[tuple[crossmarket_agentgym.agents.providers.mock.MockTurn, ...], ...] = ())
```

## `crossmarket_agentgym.agents.ConstraintFusionResult`

Proof that Agent budgets only tightened administrator constraints.

```text
(*, hard_environment: crossmarket_agentgym.environments.config.EnvironmentConfig, effective_environment: crossmarket_agentgym.environments.config.EnvironmentConfig, constraints: crossmarket_agentgym.agents.directives.EffectiveConstraintSet, risk: crossmarket_agentgym.agents.directives.RiskMergeResult, hierarchical: crossmarket_agentgym.agents.directives.HierarchicalDirective | None, cash_floor_derivation: crossmarket_agentgym.agents.directives.CashFloorDerivation, tightened_fields: tuple[str, ...])
```

## `crossmarket_agentgym.agents.DecisionConstraints`

Optional structured limits that conservative arbitration can intersect.

```text
(*, cash_floor: float | None = None, max_asset_weight: float | None = None, max_market_weights: dict[str, float] = <factory>, max_turnover: float | None = None, allow_new_positions: bool | None = None)
```

## `crossmarket_agentgym.agents.DirectiveProjection`

Projected DRL action; this object contains no account mutation method.

```text
(*, raw_action: tuple[float, ...], normalized_weights: tuple[float, ...], projected_weights: tuple[float, ...], clipping_reasons: tuple[str, ...], unresolved_constraints: tuple[str, ...], dominant_projection_reason: str, secondary_projection_reasons: tuple[str, ...], fusion: crossmarket_agentgym.agents.directives.ConstraintFusionResult)
```

## `crossmarket_agentgym.agents.HierarchicalDirective`

Third-layer low-frequency market and objective budget.

```text
(*, market_regime: Literal['risk_on', 'neutral', 'risk_off', 'high_volatility', 'unknown'], market_budgets: dict[str, float] = <factory>, sector_budgets: dict[str, float] | None = None, global_risk_budget: float, rebalance_interval: int, objective_weights: dict[str, float], confidence: float)
```

## `crossmarket_agentgym.agents.LLMLayersConfig`

Three independently switchable layers.

```text
(*, research: crossmarket_agentgym.agents.layer_config.ResearchLayerConfig = <factory>, risk: crossmarket_agentgym.agents.layer_config.RiskLayerConfig = <factory>, hierarchical: crossmarket_agentgym.agents.layer_config.HierarchicalLayerConfig = <factory>)
```

## `crossmarket_agentgym.agents.Phase7RunConfig`

Complete CPU-first three-layer fusion acceptance configuration.

```text
(*, run_id: str = 'phase7-full-stack-offline', workspace_root: pathlib.Path = '.', output_dir: pathlib.Path = 'runs', prompt_version: str = 'phase7.v1', seed: int = 1024, load_entry_points: bool = True, preset: Literal['no_llm', 'research_only', 'risk_only', 'hierarchical_only', 'research_plus_risk', 'full_stack', 'custom'], objective: str, research_payload: dict[str, Any] = <factory>, risk_context: crossmarket_agentgym.agents.directives.RiskContext | None = None, hierarchical_features: dict[str, float] = <factory>, as_of_index: int = 0, layers: crossmarket_agentgym.agents.layer_config.LLMLayersConfig, administrator_environment: crossmarket_agentgym.environments.config.EnvironmentConfig = <factory>, market_membership: tuple[Literal['CN', 'HK', 'JP', 'US'], ...], raw_action: tuple[float, ...], current_weights: tuple[float, ...], tradable_mask: tuple[bool, ...], verify_directive_replay: bool = True)
```

## `crossmarket_agentgym.agents.ResearchDirective`

First-layer plan or bounded execution directive.

```text
(*, objective: str, mode: Literal['plan_only', 'dry_run', 'execute'], steps: tuple[crossmarket_agentgym.agents.directives.ResearchStep, ...] = (), validation_only: Literal[True] = True, test_metrics_accessed: Literal[False] = False, safe_to_execute: bool = False, estimated_compute_units: float = 0.0, rationale: str, confidence: float = 0.0)
```

## `crossmarket_agentgym.agents.ResearchStep`

One schema-validated research action; execution still requires a registered tool.

```text
(*, id: str, action: Literal['inspect_dataset', 'validate_dataset', 'list_markets', 'list_symbols', 'create_split', 'validate_experiment_config', 'estimate_compute_budget', 'train_rl', 'tune_rl', 'evaluate_checkpoint', 'compare_runs', 'generate_report'], arguments: dict[str, Any] = <factory>, depends_on: tuple[str, ...] = (), expected_artifacts: tuple[str, ...] = ())
```

## `crossmarket_agentgym.agents.RiskContext`

Structured portfolio evidence visible to the risk layer.

```text
(*, portfolio_value: float, current_drawdown: float, rolling_volatility: float, rolling_cvar: float, turnover: float, market_exposures: dict[str, float] = <factory>, asset_exposures: dict[str, float] = <factory>, liquidity_flags: dict[str, bool] = <factory>, regime_features: dict[str, float] = <factory>)
```

## `crossmarket_agentgym.agents.RiskDirective`

Second-layer bounded risk proposal.

```text
(*, risk_budget: float, max_asset_weight: float, max_market_weights: dict[str, float] = <factory>, cash_floor: float, max_turnover: float, allow_new_positions: bool, rebalance_frequency: Literal['daily', 'weekly', 'monthly'], rationale: str, confidence: float)
```

## `crossmarket_agentgym.agents.RiskMergeResult`

Auditable proposed/effective risk directive and every clipped field.

```text
(*, mode: Literal['advisory', 'enforced'], proposed: crossmarket_agentgym.agents.directives.RiskDirective | None, effective: crossmarket_agentgym.agents.directives.RiskDirective, administrator_policy: crossmarket_agentgym.agents.directives.AdministratorRiskPolicy, clipped_fields: tuple[str, ...] = ())
```

## `crossmarket_agentgym.agents.TeamAggregate`

Deterministic structured team resolution.

```text
(*, status: Literal['resolved', 'rejected', 'no_quorum'], policy: Literal['weighted_vote', 'majority_vote', 'judge', 'most_conservative', 'reject'], configured_conflict_policy: Literal['weighted_vote', 'majority_vote', 'judge', 'most_conservative', 'reject'], conflict_detected: bool, aggregate_decision: Literal['approve', 'revise', 'reject', 'abstain'], selected_directive_confidence: float, committee_confidence: float, confidence_aggregation: Literal['minimum'] = 'minimum', decision: crossmarket_agentgym.agents.models.AgentDecision, participants: tuple[str, ...], failed_instances: tuple[str, ...] = ())
```

## `crossmarket_agentgym.agents.TeamRunResult`

Serializable result shared by single-Agent and multi-Agent runs.

```text
(*, schema_version: Literal['1.0'] = '1.0', run_id: str, topology: Literal['single', 'pipeline', 'supervisor_worker', 'committee_vote', 'debate_then_judge', 'map_reduce'], configured_instances: int, invocations: int, succeeded: int, fallback: int, failed: int, timed_out: int, rounds: int, parallel: bool, network_used: bool, results: tuple[crossmarket_agentgym.agents.models.AgentExecutionResult, ...], aggregate: crossmarket_agentgym.agents.models.TeamAggregate)
```

## `crossmarket_agentgym.agents.TeamSpec`

Communication topology and deterministic arbitration policy.

```text
(*, topology: Literal['single', 'pipeline', 'supervisor_worker', 'committee_vote', 'debate_then_judge', 'map_reduce'], agents: tuple[crossmarket_agentgym.agents.models.AgentSpec, ...], supervisor: str | None = None, judge: str | None = None, max_rounds: int = 3, quorum: float = 0.5, conflict_policy: Literal['weighted_vote', 'majority_vote', 'judge', 'most_conservative', 'reject'] = 'most_conservative', parallel: bool = True, max_workers: int = 8)
```

## `crossmarket_agentgym.agents.execute_agent_runtime`

Execute a single or team run without silently replacing any Provider.

```text
(config: 'AgentRuntimeConfig', *, registry: 'AgentRegistry | None' = None, tool_registry: 'ToolRegistry | None' = None) -> 'TeamRunResult'
```

## `crossmarket_agentgym.agents.execute_phase7_stack`

Run enabled layers, intersect hard limits, project once, and verify Replay.

```text
(config: 'Phase7RunConfig', *, registry: 'AgentRegistry | None' = None, tool_registry: 'ToolRegistry | None' = None) -> 'Phase7RunSummary'
```

## `crossmarket_agentgym.agents.expand_agent_specs`

Expand enabled specs in configuration order with stable IDs and seeds.

```text
(config: 'AgentRuntimeConfig') -> 'tuple[AgentInstance, ...]'
```

## `crossmarket_agentgym.agents.fuse_constraint_directives`

Build a stricter immutable EnvironmentConfig; never widen hard limits.

```text
(*, environment: 'EnvironmentConfig', markets: 'tuple[Market, ...]', risk: 'RiskMergeResult', hierarchical: 'HierarchicalDirective | None') -> 'ConstraintFusionResult'
```

## `crossmarket_agentgym.agents.load_phase7_run_config`

Load strict YAML without resolving credentials or constructing Providers.

```text
(path: 'Path') -> 'Phase7RunConfig'
```

## `crossmarket_agentgym.agents.merge_risk_directive`

Intersect LLM advice with hard policy; advisory mode cannot change limits.

```text
(proposed: 'RiskDirective | None', *, policy: 'AdministratorRiskPolicy', markets: 'tuple[str, ...]', mode: 'RiskMode') -> 'RiskMergeResult'
```

## `crossmarket_agentgym.agents.project_with_directives`

Apply Agent-derived tighter limits through the existing deterministic projector.

```text
(raw_action: 'tuple[float, ...]', *, current_weights: 'tuple[float, ...]', tradable_mask: 'tuple[bool, ...]', markets: 'tuple[Market, ...]', fusion: 'ConstraintFusionResult') -> 'DirectiveProjection'
```

## `crossmarket_agentgym.agents.replay_phase7_bundle`

Recompute hard merge and projection from recorded validated directives only.

```text
(bundle_path: 'Path') -> 'DirectiveProjection'
```

## `crossmarket_agentgym.config.LLMConfig`

Credential-free metadata for the required OpenAI-compatible provider.

```text
(*, provider: Literal['openai_compatible'] = 'openai_compatible', model: str = 'deepseek-v4-pro', api_key_env: str = 'DEEPSEEK_API_KEY', base_url_env: str = 'DEEPSEEK_BASE_URL', temperature: float = 0.0, max_tokens: int = 2048, timeout_seconds: int = 120, max_retries: int = 2, retry_backoff_seconds: float = 0.25, structured_output_mode: Literal['json_object', 'json_schema'] = 'json_object')
```

## `crossmarket_agentgym.config.ProjectConfig`

Reproducible project-level settings.

```text
(*, name: str = 'crossmarket_agent_gym', seed: int = 1024, output_dir: pathlib.Path = 'runs')
```

## `crossmarket_agentgym.config.RootConfig`

Minimal root configuration expanded in later phases.

```text
(*, project: crossmarket_agentgym.config.models.ProjectConfig = <factory>, llm: crossmarket_agentgym.config.models.LLMConfig = <factory>)
```

## `crossmarket_agentgym.config.load_config`

Load and validate a YAML file without executable YAML extensions.

```text
(path: 'Path') -> 'RootConfig'
```

## `crossmarket_agentgym.data.CanonicalLoadResult`

A loaded frame and the non-destructive report produced for it.

```text
(frame: 'pd.DataFrame', report: 'DataQualityReport', path: 'Path') -> None
```

## `crossmarket_agentgym.data.DatasetValidationSummary`

Auditable validation status across all inspected source files.

```text
(*, is_valid: bool, root: str, layout: str, markets: list[str], files_checked: int, ohlcv_rows: int, quality: crossmarket_agentgym.data.quality.report.DataQualityReport, manifest_missing: list[str] = <factory>, manifest_hash_mismatches: list[str] = <factory>, manifest_size_mismatches: list[str] = <factory>)
```

## `crossmarket_agentgym.data.PartitionAccessError`

Raised when a workflow receives the wrong dataset capability.

```text
class
```

## `crossmarket_agentgym.data.PartitionCapability`

Immutable authority to use one closed transition interval.

```text
(*, dataset_id: str, partition: Literal['train', 'validation', 'test', 'smoke'], start_signal_index: int, end_execution_index: int)
```

## `crossmarket_agentgym.data.PartitionName`

Stable exported integration symbol.

```text
(*args, **kwargs)
```

## `crossmarket_agentgym.data.load_canonical`

Load canonical CSV or Parquet and optionally reject its quality report.

```text
(path: 'Path', *, require_valid: 'bool' = False) -> 'CanonicalLoadResult'
```

## `crossmarket_agentgym.data.manifests.DatasetManifest`

Reproducible metadata for a canonical dataset root.

```text
(*, schema_version: str = '1.0.0', dataset_name: str, created_at: datetime.datetime, software_version: str, source: str, adjustment_rule: str, row_count: int, markets: list[str], symbols: list[str], date_start: str | None, date_end: str | None, schema_columns: list[str], files: list[crossmarket_agentgym.data.manifests.models.ManifestFile], quality: crossmarket_agentgym.data.manifests.models.QualitySummary)
```

## `crossmarket_agentgym.data.manifests.FileRole`

Stable exported integration symbol.

```text
(*args, **kwargs)
```

## `crossmarket_agentgym.data.manifests.ManifestFile`

Integrity and semantic metadata for one dataset artifact.

```text
(*, path: str, role: Literal['ohlcv', 'instruments', 'fx'], format: Literal['csv', 'parquet'], size_bytes: int, sha256: str, row_count: int, markets: list[str] = <factory>, symbols: list[str] = <factory>, date_start: str | None = None, date_end: str | None = None)
```

## `crossmarket_agentgym.data.manifests.ManifestVerification`

Recomputed filesystem integrity results.

```text
(*, missing_files: list[str] = <factory>, hash_mismatches: list[str] = <factory>, size_mismatches: list[str] = <factory>)
```

## `crossmarket_agentgym.data.manifests.QualitySummary`

Aggregated validation status captured at import time.

```text
(*, is_valid: bool, error_count: int, warning_count: int)
```

## `crossmarket_agentgym.data.manifests.build_dataset_manifest`

Build a manifest from existing files and their recomputed quality metadata.

```text
(*, root: 'Path', dataset_name: 'str', file_roles: 'Mapping[Path, FileRole]', source: 'str', adjustment_rule: 'str', created_at: 'datetime | None' = None) -> 'DatasetManifest'
```

## `crossmarket_agentgym.data.manifests.load_manifest`

Load and validate a dataset manifest.

```text
(path: 'Path') -> 'DatasetManifest'
```

## `crossmarket_agentgym.data.manifests.sha256_file`

Return the SHA-256 digest of a file without loading it all into memory.

```text
(path: 'Path') -> 'str'
```

## `crossmarket_agentgym.data.manifests.verify_manifest`

Recompute sizes and hashes without changing recorded metadata.

```text
(root: 'Path', manifest: 'DatasetManifest') -> 'ManifestVerification'
```

## `crossmarket_agentgym.data.manifests.write_manifest`

Write stable, human-readable UTF-8 JSON.

```text
(manifest: 'DatasetManifest', path: 'Path') -> 'None'
```

## `crossmarket_agentgym.data.require_partition`

Reject a partition unless the caller explicitly allows it.

```text
(capability: 'PartitionCapability', allowed: 'frozenset[PartitionName]') -> 'None'
```

## `crossmarket_agentgym.data.schemas.CANONICAL_COLUMNS`

Built-in immutable sequence.

```text
constant_or_type_alias
```

## `crossmarket_agentgym.data.schemas.MARKET_METADATA`

dict() -> new empty dictionary

```text
constant_or_type_alias
```

## `crossmarket_agentgym.data.schemas.Market`

Stable exported integration symbol.

```text
(*args, **kwargs)
```

## `crossmarket_agentgym.data.schemas.MarketMetadata`

Stable metadata that can be validated without guessing an exchange.

```text
(currency: 'str', timezone: 'str', default_exchange: 'str') -> None
```

## `crossmarket_agentgym.data.schemas.OHLCVRecord`

One local-market daily bar with explicit provenance and adjustment state.

```text
(*, trade_date: datetime.date, symbol: str, market: Literal['CN', 'HK', 'JP', 'US'], exchange: str, open: float, high: float, low: float, close: float, volume: float, currency: str, timezone: str, adjusted: bool, source: str, adjusted_close: float | None = None, turnover: float | None = None, suspension_flag: bool | None = None, limit_up: bool | None = None, limit_down: bool | None = None, tradable: bool | None = None)
```

## `crossmarket_agentgym.data.schemas.OPTIONAL_COLUMNS`

Built-in immutable sequence.

```text
constant_or_type_alias
```

## `crossmarket_agentgym.data.schemas.REQUIRED_COLUMNS`

Built-in immutable sequence.

```text
constant_or_type_alias
```

## `crossmarket_agentgym.data.validate_configured_dataset`

Dispatch validation according to a strict data configuration.

```text
(config: 'DataValidationConfig', *, max_files_per_market: 'int | None' = None) -> 'DatasetValidationSummary'
```

## `crossmarket_agentgym.data.validate_legacy_dataset`

Normalize and inspect legacy sources without editing or dropping their rows.

```text
(root: 'Path', *, max_files_per_market: 'int | None' = None, directory_markets: 'Mapping[str, Market] | None' = None) -> 'DatasetValidationSummary'
```

## `crossmarket_agentgym.data.validate_manifest_dataset`

Validate every OHLCV artifact and recompute every manifest digest.

```text
(root: 'Path') -> 'DatasetValidationSummary'
```

## `crossmarket_agentgym.data.write_canonical`

Validate and write canonical CSV or Parquet without sorting or row deletion.

```text
(frame: 'pd.DataFrame', path: 'Path', *, require_valid: 'bool' = True) -> 'DataQualityReport'
```

## `crossmarket_agentgym.environments.ConstraintProjector`

Apply a fixed, replayable sequence of hard portfolio rules.

```text
(config: 'EnvironmentConfig', markets: 'tuple[Market, ...]') -> 'None'
```

## `crossmarket_agentgym.environments.CrossMarketPortfolioEnv`

Daily portfolio environment using close signals and next-open execution.

```text
(panel: 'MarketDataPanel', config: 'EnvironmentConfig', *, render_mode: "Literal['human', 'ansi', 'rgb_array'] | None" = None, partition: 'PartitionCapability | None' = None, observation: 'ObservationConfig | None' = None) -> 'None'
```

## `crossmarket_agentgym.environments.EnvironmentCheckConfig`

Strict configuration for `cmag env check`.

```text
(*, dataset_root: pathlib.Path, seed: int = 1024, smoke_steps: int = 1000, observation: crossmarket_agentgym.environments.observations.ObservationConfig = <factory>, environment: crossmarket_agentgym.environments.config.EnvironmentConfig = <factory>)
```

## `crossmarket_agentgym.environments.EnvironmentCheckSummary`

Serializable evidence from compatibility and random-action checks.

```text
(*, is_valid: bool, gymnasium_check: Literal['passed'], sb3_check: Literal['passed', 'skipped_not_installed'], smoke_steps: int, resets: int, finite_observations: bool, finite_rewards: bool, finite_values: bool, max_accounting_error: float, min_portfolio_value: float, execution_protocol: str, market_window_layout: Literal['flat', 'tensor'], warnings: tuple[crossmarket_agentgym.environments.checks.EnvironmentCheckWarning, ...] = ())
```

## `crossmarket_agentgym.environments.EnvironmentCheckWarning`

One accepted or blocking compatibility warning.

```text
(*, warning_code: str, accepted: bool, reason: str, required_policy: str | None = None)
```

## `crossmarket_agentgym.environments.EnvironmentConfig`

Immutable hard constraints and daily execution settings.

```text
(*, execution_protocol: Literal['close_signal_next_open'] = 'close_signal_next_open', base_currency: str = 'USD', lookback: int = 20, initial_cash: float = 1000000.0, allow_short: bool = False, max_leverage: float = 1.0, max_asset_weight: float = 0.1, max_market_weight: float = 0.4, market_weight_overrides: dict[Literal['CN', 'HK', 'JP', 'US'], float] = <factory>, cash_floor: float = 0.05, max_turnover: float = 1.0, transaction_cost_bps: float = 10.0, slippage_bps: float = 5.0, reward: Literal['log_return', 'return_minus_cost', 'risk_adjusted', 'differential_sharpe', 'drawdown_penalty', 'cvar_penalty'] = 'risk_adjusted', risk_aversion: float = 0.1, drawdown_penalty: float = 0.5, cvar_alpha: float = 0.05, cvar_penalty: float = 0.5, lot_sizes: dict[str, int] = <factory>, t_plus_one_markets: frozenset[Literal['CN', 'HK', 'JP', 'US']] = frozenset({'CN'}), max_episode_steps: int | None = None, accounting_tolerance: float = 1e-08)
```

## `crossmarket_agentgym.environments.MarketDataPanel`

Dense daily arrays aligned on a union calendar.

```text
(dates: 'tuple[date, ...]', symbols: 'tuple[str, ...]', markets: 'tuple[Market, ...]', currencies: 'tuple[str, ...]', market_ids: 'NDArray[np.int32]', currency_ids: 'NDArray[np.int32]', features: 'NDArray[np.float32]', open_prices: 'NDArray[np.float64]', close_prices: 'NDArray[np.float64]', tradable_mask: 'NDArray[np.bool_]', suspension_mask: 'NDArray[np.bool_]', limit_up_mask: 'NDArray[np.bool_]', limit_down_mask: 'NDArray[np.bool_]', first_fully_valued_index: 'int', base_currency: 'str', feature_names: 'tuple[str, ...]' = ('open_base', 'high_base', 'low_base', 'close_base', 'volume', 'log_return_base')) -> None
```

## `crossmarket_agentgym.environments.MarketWindowLayout`

Stable exported integration symbol.

```text
(*args, **kwargs)
```

## `crossmarket_agentgym.environments.ObservationConfig`

Presentation layout for the raw ``[N,L,F]`` financial tensor.

```text
(*, market_window_layout: Literal['flat', 'tensor'] = 'tensor')
```

## `crossmarket_agentgym.environments.RewardName`

Stable exported integration symbol.

```text
(*args, **kwargs)
```

## `crossmarket_agentgym.environments.run_environment_checks`

Run Gymnasium/SB3 checks and a seeded random-action accounting smoke test.

```text
(config: 'EnvironmentCheckConfig') -> 'EnvironmentCheckSummary'
```

## `crossmarket_agentgym.evaluation.BASELINES`

dict() -> new empty dictionary

```text
constant_or_type_alias
```

## `crossmarket_agentgym.evaluation.BaselineStrategy`

Stateful baseline contract compatible with the evaluator.

```text
(*args, **kwargs)
```

## `crossmarket_agentgym.evaluation.EvaluationResult`

Metrics and replayable step records for one evaluated policy.

```text
(*, schema_version: Literal['1.0'] = '1.0', algorithm: str, partition: str, episodes: int, evaluation_episodes: int, return_sample_count: int, reward_sample_count: int, statistical_warnings: tuple[str, ...] = (), total_steps: int, metrics: dict[str, float], trades: list[crossmarket_agentgym.evaluation.results.TradeRecord], weights: list[crossmarket_agentgym.evaluation.results.WeightRecord])
```

## `crossmarket_agentgym.evaluation.TradeRecord`

One environment transition's executed trade audit.

```text
(*, schema_version: Literal['1.0'] = '1.0', episode: int, step: int, signal_date: str, execution_date: str, quantities: list[float], trade_value: float, transaction_cost: float, slippage: float, turnover: float)
```

## `crossmarket_agentgym.evaluation.WeightRecord`

One projected and realized portfolio record.

```text
(*, schema_version: Literal['1.0'] = '1.0', episode: int, step: int, execution_date: str, projected: list[float], realized: list[float], portfolio_value: float, drawdown: float)
```

## `crossmarket_agentgym.evaluation.baseline_by_name`

Construct an approved baseline by stable name.

```text
(name: 'str') -> 'BaselineStrategy'
```

## `crossmarket_agentgym.evaluation.evaluate_policy`

Evaluate without granting a training path to validation/test metrics.

```text
(env: 'gym.Env[dict[str, NDArray[Any]], NDArray[np.float32]]', predictor: 'Predictor', *, algorithm: 'str', episodes: 'int' = 1, deterministic: 'bool' = True, seed: 'int' = 1024) -> 'EvaluationResult'
```

## `crossmarket_agentgym.evaluation.write_evaluation_artifacts`

Write metrics, trades, and weights as separate deterministic JSON files.

```text
(result: 'EvaluationResult', output_dir: 'Path') -> 'None'
```

## `crossmarket_agentgym.features.StandardizationState`

Serializable feature statistics learned from training data only.

```text
(mean: 'NDArray[np.float64]', scale: 'NDArray[np.float64]', dataset_id: 'str') -> None
```

## `crossmarket_agentgym.features.TrainOnlyStandardizer`

Fit standardization statistics only with a training capability.

```text
(epsilon: 'float' = 1e-08) -> 'None'
```

## `crossmarket_agentgym.release.build_release_manifest`

Hash built wheels and source archives without publishing them.

```text
(dist_dir: 'str | Path') -> 'DistributionManifest'
```

## `crossmarket_agentgym.release.check_release_readiness`

Validate local release assets without uploading or tagging anything.

```text
(workspace_root: 'str | Path' = '.') -> 'ReleaseReadinessResult'
```

## `crossmarket_agentgym.release.is_release_candidate`

Return whether the accepted release version is an rc build.

```text
(version: 'str') -> 'bool'
```

## `crossmarket_agentgym.release.release_label`

Return the human/tag label for one accepted PEP 440 release version.

```text
(version: 'str') -> 'str'
```

## `crossmarket_agentgym.release.release_tag`

Return the required Git tag for one accepted release version.

```text
(version: 'str') -> 'str'
```

## `crossmarket_agentgym.release.reproduce_run`

Verify one known run without network, retraining, or account mutation.

```text
(workspace_root: 'str | Path', runs_root: 'str | Path', run_id: 'str', *, max_json_bytes: 'int' = 5000000) -> 'ReproductionResult'
```

## `crossmarket_agentgym.release.run_cpu_quickstart`

Validate the four-market sample and run seeded environment checks.

```text
(workspace_root: 'str | Path' = '.', *, smoke_steps: 'int' = 64) -> 'CpuQuickstartSummary'
```

## `crossmarket_agentgym.release.verify_distributions`

Verify metadata, packaged quickstart assets, and archive exclusions.

```text
(dist_dir: 'str | Path', *, expected_version: 'str | None' = None) -> 'DistributionVerificationResult'
```

## `crossmarket_agentgym.rl.AlgorithmName`

Stable exported integration symbol.

```text
(*args, **kwargs)
```

## `crossmarket_agentgym.rl.CallbackConfig`

Cadence and thresholds for every required training callback.

```text
(*, checkpoint_freq: int = 250, validation_freq: int = 250, early_stop_patience: int = 5, finite_guard: bool = True, max_drawdown: float | None = 0.8, resource_monitor_freq: int = 100, audit_freq: int = 1, metrics_freq: int = 1)
```

## `crossmarket_agentgym.rl.RLTrainer`

Common training, evaluation, save, and load contract.

```text
(*args, **kwargs)
```

## `crossmarket_agentgym.rl.SB3Trainer`

Algorithm-neutral implementation of the project trainer protocol.

```text
(algorithm: 'AlgorithmName', run_dir: 'Path') -> 'None'
```

## `crossmarket_agentgym.rl.TemporalSplitConfig`

Non-overlapping outcome intervals with shared boundary observations.

```text
(*, train_end_execution_index: int, validation_end_execution_index: int, test_end_execution_index: int | None = None)
```

## `crossmarket_agentgym.rl.TrainRunConfig`

Complete local training workflow configuration.

```text
(*, dataset_root: pathlib.Path, output_dir: pathlib.Path = 'runs', run_name: str = 'ppo_cpu_quickstart', observation: crossmarket_agentgym.environments.observations.ObservationConfig = <factory>, environment: crossmarket_agentgym.environments.config.EnvironmentConfig = <factory>, split: crossmarket_agentgym.rl.config.TemporalSplitConfig, trainer: crossmarket_agentgym.rl.config.TrainerConfig = <factory>, callbacks: crossmarket_agentgym.rl.config.CallbackConfig = <factory>)
```

## `crossmarket_agentgym.rl.TrainerConfig`

Algorithm and policy settings shared by every SB3 trainer.

```text
(*, algorithm: Literal['PPO', 'SAC', 'TD3', 'A2C'] = 'PPO', policy: Literal['mlp', 'shared_mlp', 'transformer'] = 'shared_mlp', total_timesteps: int = 1000, learning_rate: float = 0.0003, gamma: float = 0.99, n_steps: int = 64, batch_size: int = 32, n_epochs: int = 4, buffer_size: int = 10000, learning_starts: int = 10, train_freq: int = 1, gradient_steps: int = 1, tau: float = 0.005, features_dim: int = 64, net_arch: tuple[int, ...] = (64, 64), transformer_model_dim: int = 32, transformer_heads: int = 4, transformer_layers: int = 1, action_noise_std: float = 0.1, device: Literal['auto', 'cpu', 'cuda'] = 'cpu', seed: int = 1024, deterministic_eval: bool = True, eval_episodes: int = 1, verbose: int = 0)
```

## `crossmarket_agentgym.rl.TrainingArtifact`

In-memory model plus its persisted metadata and paths.

```text
(model: 'Any', metadata: 'TrainingMetadata', run_dir: 'Path', checkpoint_path: 'Path') -> None
```

## `crossmarket_agentgym.rl.TrainingMetadata`

Credential-free checkpoint provenance.

```text
(*, schema_version: Literal['1.0'] = '1.0', algorithm: str, policy: str, requested_timesteps: int, trained_timesteps: int, seed: int, config_sha256: str, checkpoint: str, dataset_id: str, data_partition: str, dependencies: dict[str, str])
```

## `crossmarket_agentgym.rl.TrainingRunSummary`

Serializable CLI result for a completed training run.

```text
(*, schema_version: Literal['1.0'] = '1.0', run_id: str, run_dir: str, algorithm: str, checkpoint: str, requested_timesteps: int, trained_timesteps: int, validation_metrics: dict[str, float], started_at: datetime.datetime, finished_at: datetime.datetime, runtime_seconds: float, training_runtime_seconds: float, evaluation_runtime_seconds: float, device: str, torch_version: str, python_version: str, cpu_model: str, gpu_model: str | None)
```

## `crossmarket_agentgym.rl.build_partitioned_environments`

Build disjoint outcome intervals over one verified market panel.

```text
(config: 'TrainRunConfig', *, include_test: 'bool' = True) -> 'dict[str, CrossMarketPortfolioEnv]'
```

## `crossmarket_agentgym.rl.evaluate_saved_run`

Evaluate a saved checkpoint once on validation or locked test data.

```text
(run_dir: 'Path', *, partition: "Literal['validation', 'test']" = 'test', config_override: 'TrainRunConfig | None' = None) -> 'EvaluationResult'
```

## `crossmarket_agentgym.rl.execute_training_run`

Train on train, select on validation, and never read test.

```text
(config: 'TrainRunConfig') -> 'TrainingRunSummary'
```

## `crossmarket_agentgym.rl.load_train_run_config`

Load a strict YAML training configuration.

```text
(path: 'Path') -> 'TrainRunConfig'
```

## `crossmarket_agentgym.rl.trainer_from_config`

Construct the unified trainer for an approved algorithm.

```text
(config: 'TrainerConfig', run_dir: 'Path') -> 'SB3Trainer'
```

## `crossmarket_agentgym.tuning.Direction`

Stable exported integration symbol.

```text
(*args, **kwargs)
```

## `crossmarket_agentgym.tuning.FunctionalObjective`

Adapt a pure callable to the objective evaluator contract.

```text
(function: 'Callable[[dict[str, Any]], float | tuple[float, ...]]', *, resource: 'float' = 1.0) -> 'None'
```

## `crossmarket_agentgym.tuning.LocalTrialExecutor`

Evaluate in configuration order on the current process.

```text
()
```

## `crossmarket_agentgym.tuning.ObjectiveEvaluator`

Serializable or local objective evaluation boundary.

```text
(*args, **kwargs)
```

## `crossmarket_agentgym.tuning.ParameterSpec`

One scalar, categorical, or conditional search parameter.

```text
(*, name: str, kind: Literal['float', 'int', 'categorical', 'bool'], low: float | int | None = None, high: float | int | None = None, choices: tuple[Any, ...] | None = None, log: bool = False, step: float | int | None = None, condition: str | None = None)
```

## `crossmarket_agentgym.tuning.SQLiteStudyStore`

Durable study, trial, and component-checkpoint store.

```text
(path: 'str | Path') -> 'None'
```

## `crossmarket_agentgym.tuning.SearchSpace`

Ordered mixed search space with safe conditional constraints.

```text
(*, parameters: tuple[crossmarket_agentgym.tuning.models.ParameterSpec, ...], constraints: tuple[str, ...] = ())
```

## `crossmarket_agentgym.tuning.StudyState`

Search history visible to initialization and reports.

```text
(*, schema_version: Literal['1.0'] = '1.0', study_name: str, directions: tuple[Literal['maximize', 'minimize'], ...] = ('maximize',), results: tuple[crossmarket_agentgym.tuning.models.TrialResult, ...] = ())
```

## `crossmarket_agentgym.tuning.TrialBatchExecutor`

Evaluate suggestions without generating or scheduling them.

```text
(*args, **kwargs)
```

## `crossmarket_agentgym.tuning.TrialResult`

Completed, failed, or pruned trial result.

```text
(*, schema_version: Literal['1.0'] = '1.0', trial_id: int, parameters: dict[str, Any], status: Literal['pending', 'running', 'completed', 'failed', 'pruned'], objectives: tuple[float, ...] = (), metrics: dict[str, float] = <factory>, resource: float = 0.0, error: str | None = None)
```

## `crossmarket_agentgym.tuning.TrialRunner`

Persisted CPU-first driver shared by every search/scheduler pairing.

```text
(*, study_name: 'str', directions: 'tuple[Direction, ...]', search_space: 'SearchSpace', searcher: 'SearchAlgorithm', scheduler: 'TrialScheduler', evaluator: 'ObjectiveEvaluator', store: 'SQLiteStudyStore', batch_size: 'int' = 1, study_metadata: 'dict[str, Any] | None' = None, executor: 'TrialBatchExecutor | None' = None) -> 'None'
```

## `crossmarket_agentgym.tuning.TrialSuggestion`

One candidate emitted by a search algorithm.

```text
(*, schema_version: Literal['1.0'] = '1.0', trial_id: int, parameters: dict[str, Any], generation: int = 0, metadata: dict[str, Any] = <factory>)
```

## `crossmarket_agentgym.tuning.dominates`

Return Pareto dominance under mixed objective directions.

```text
(first: 'TrialResult', second: 'TrialResult', directions: 'tuple[Direction, ...]') -> 'bool'
```

## `crossmarket_agentgym.tuning.scalar_utility`

Convert the first objective into a maximize-oriented utility.

```text
(result: 'TrialResult', directions: 'tuple[Direction, ...]') -> 'float'
```
