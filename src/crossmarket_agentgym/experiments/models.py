"""Strict models for the immutable Phase 12 experiment protocol."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_CORE_HPO = frozenset(
    {
        "default",
        "random",
        "tpe",
        "cma_es",
        "pso",
        "genetic",
        "differential_evolution",
        "nsga_ii",
    }
)


class FrozenExperimentModel(BaseModel):
    """Reject unknown protocol fields and runtime mutation."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DateInterval(FrozenExperimentModel):
    """Inclusive calendar interval."""

    start: date
    end: date

    @model_validator(mode="after")
    def validate_order(self) -> DateInterval:
        """Reject empty or reversed time intervals."""
        if self.end < self.start:
            raise ValueError("date interval end must not precede start")
        return self


class WalkForwardFold(FrozenExperimentModel):
    """One expanding-window train/validation fold."""

    fold_id: str = Field(pattern=r"^fold_[0-9]{2}$")
    train: DateInterval
    validation: DateInterval

    @model_validator(mode="after")
    def validate_temporal_separation(self) -> WalkForwardFold:
        """Require validation to follow training without overlap."""
        if self.train.end >= self.validation.start:
            raise ValueError("walk-forward validation must start after training")
        return self


class DatasetSelectionProtocol(FrozenExperimentModel):
    """Deterministic, quality-gated stock-universe selection."""

    markets: tuple[Literal["CN", "HK", "JP", "US"], ...]
    assets_per_market: int = Field(ge=2)
    held_out_assets_per_market: int = Field(ge=1)
    ordering: Literal["sha256_market_symbol_salt"]
    ordering_salt: str = Field(min_length=1)
    reject_source_on_any_quality_error: Literal[True] = True
    allow_row_repair: Literal[False] = False
    allowed_semantic_exclusions: tuple[
        Literal["non_ohlcv_record_with_all_price_volume_fields_missing"], ...
    ]
    minimum_source_coverage: DateInterval
    experiment_window: DateInterval
    universe_formation_date: date | None = None
    selection_information_cutoff: date | None = None
    post_cutoff_quality_policy: Literal[
        "retain_symbol_censor_from_first_invalid_observation"
    ] | None = None
    survivorship_bias_disclosed: Literal[True] = True

    @field_validator("markets")
    @classmethod
    def validate_markets(
        cls,
        markets: tuple[Literal["CN", "HK", "JP", "US"], ...],
    ) -> tuple[Literal["CN", "HK", "JP", "US"], ...]:
        """Require all four markets once and in canonical order."""
        if markets != ("CN", "HK", "JP", "US"):
            raise ValueError("formal protocol requires markets [CN, HK, JP, US]")
        return markets

    @model_validator(mode="after")
    def validate_universe_geometry(self) -> DatasetSelectionProtocol:
        """Reserve at least one training asset in every market."""
        if self.held_out_assets_per_market >= self.assets_per_market:
            raise ValueError("held-out assets must be fewer than selected assets")
        coverage = self.minimum_source_coverage
        window = self.experiment_window
        if coverage.start > window.start:
            raise ValueError("minimum source coverage must start by experiment window")
        cutoff = self.selection_information_cutoff
        formation = self.universe_formation_date
        if cutoff is None and formation is None:
            if coverage.end < window.end:
                raise ValueError("minimum source coverage must contain experiment window")
        else:
            if cutoff is None or formation is None:
                raise ValueError("formation date and information cutoff must be paired")
            if cutoff != formation or coverage.end < cutoff:
                raise ValueError("coverage must reach the frozen universe cutoff")
            if self.post_cutoff_quality_policy is None:
                raise ValueError("post-cutoff quality policy is required")
        return self


class DatasetProtocol(FrozenExperimentModel):
    """Source inventory and immutable processed-dataset contract."""

    dataset_version: Literal[
        "dataset-manifest-v1",
        "dataset-manifest-v2",
        "dataset-manifest-v3",
    ]
    source_root: Path
    source_inventory: Path
    source_inventory_sha256: str = Field(pattern=_SHA256_PATTERN)
    processed_root: Path
    processed_manifest: Path
    processed_manifest_sha256: str = Field(pattern=_SHA256_PATTERN)
    selection: DatasetSelectionProtocol
    corporate_action_policy: Literal[
        "raw_ohlc_with_adjusted_close_metadata_no_future_backfill"
    ]
    source_mutation_policy: Literal[
        "reject",
        "reject_invalid_observation_and_censor_all_later_observations",
    ]


class FXProtocol(FrozenExperimentModel):
    """Auditable ECB reference-rate acquisition and conversion rule."""

    provider: Literal["European Central Bank Data Portal"]
    dataset: Literal["EXR"]
    endpoint: str = Field(pattern=r"^https://data-api\.ecb\.europa\.eu/")
    raw_snapshot: Path
    raw_snapshot_sha256: str = Field(pattern=_SHA256_PATTERN)
    currencies: tuple[Literal["CNY", "HKD", "JPY", "USD"], ...]
    quote_currency: Literal["USD"]
    transformation: Literal["currency_to_usd=usd_per_eur/currency_per_eur"]
    lookup: Literal["latest_on_or_before"]
    acquisition_window: DateInterval

    @field_validator("currencies")
    @classmethod
    def validate_currencies(
        cls,
        currencies: tuple[Literal["CNY", "HKD", "JPY", "USD"], ...],
    ) -> tuple[Literal["CNY", "HKD", "JPY", "USD"], ...]:
        """Freeze the exact four-currency order."""
        if currencies != ("CNY", "HKD", "JPY", "USD"):
            raise ValueError("formal FX currencies must be [CNY, HKD, JPY, USD]")
        return currencies


class PartitionProtocol(FrozenExperimentModel):
    """Train/validation/test and walk-forward isolation."""

    train: DateInterval
    validation: DateInterval
    test: DateInterval
    walk_forward: tuple[WalkForwardFold, ...]
    train_usage: Literal["fit_model_and_train_only_preprocessing"]
    validation_usage: Literal["early_stopping_hpo_and_model_selection"]
    test_usage: Literal["single_locked_configuration_final_evaluation"]
    random_time_shuffle: Literal[False] = False

    @model_validator(mode="after")
    def validate_partitions(self) -> PartitionProtocol:
        """Require strict chronological, non-overlapping partitions."""
        if self.train.end >= self.validation.start:
            raise ValueError("validation must start after train")
        if self.validation.end >= self.test.start:
            raise ValueError("test must start after validation")
        if not self.walk_forward:
            raise ValueError("at least one walk-forward fold is required")
        if any(fold.validation.end > self.validation.end for fold in self.walk_forward):
            raise ValueError("walk-forward validation cannot extend into test")
        return self


class ExecutionProtocol(FrozenExperimentModel):
    """Shared accounting, market-rule, and risk constraints."""

    signal_execution: Literal["close_signal_next_open"]
    base_currency: Literal["USD"]
    initial_cash: float = Field(gt=0.0)
    transaction_cost_bps: float = Field(ge=0.0)
    slippage_bps: float = Field(ge=0.0)
    allow_short: Literal[False] = False
    max_leverage: float = Field(gt=0.0, le=1.0)
    max_asset_weight: float = Field(gt=0.0, le=1.0)
    max_market_weight: float = Field(gt=0.0, le=1.0)
    cash_floor: float = Field(ge=0.0, le=1.0)
    max_turnover: float = Field(gt=0.0, le=2.0)
    t_plus_one_markets: tuple[Literal["CN"], ...]
    asynchronous_calendar: Literal["union_observed_sessions"]
    fx_rule: Literal["latest_on_or_before"]
    risk_projection: Literal["mandatory_deterministic"]
    accounting_tolerance: float = Field(gt=0.0, le=1e-8)


class DRLProtocol(FrozenExperimentModel):
    """Frozen algorithms, policies, budgets, and search space."""

    algorithms: tuple[Literal["PPO", "SAC", "TD3"], ...]
    policy: Literal["mlp"]
    observation_layout: Literal["flat"]
    lookback: int = Field(ge=2)
    total_timesteps: int = Field(ge=1)
    evaluation_episodes: int = Field(ge=2)
    deterministic_evaluation: Literal[True] = True
    search_space: dict[str, dict[str, str | float | int | bool]]

    @field_validator("algorithms")
    @classmethod
    def validate_algorithms(
        cls,
        algorithms: tuple[Literal["PPO", "SAC", "TD3"], ...],
    ) -> tuple[Literal["PPO", "SAC", "TD3"], ...]:
        """Freeze the required strategy order."""
        if algorithms != ("PPO", "SAC", "TD3"):
            raise ValueError("formal DRL algorithms must be [PPO, SAC, TD3]")
        return algorithms


class AgentProtocol(FrozenExperimentModel):
    """Frozen online Agent provider, prompts, topology, and permissions."""

    model: Literal["deepseek-v4-pro"]
    api_key_env: Literal["DEEPSEEK_API_KEY"]
    base_url_env: Literal["DEEPSEEK_BASE_URL"]
    default_base_url: Literal["https://api.deepseek.com"]
    temperature: float = Field(ge=0.0, le=0.0)
    max_rounds: int = Field(ge=1, le=10)
    prompt_version: str = Field(min_length=1)
    prompt_source: Path | None = None
    prompt_source_sha256: str = Field(pattern=_SHA256_PATTERN)
    allowed_permissions: tuple[Literal["read", "compute"], ...]
    network_access: Literal["provider_only"]
    account_state_mutation: Literal[False] = False
    deterministic_risk_layer_bypass: Literal[False] = False
    replay_required: Literal[True] = True
    presets: tuple[str, ...]


class HPOProtocol(FrozenExperimentModel):
    """Equal-budget search comparison with scheduler separation."""

    searchers: tuple[
        Literal[
            "default",
            "random",
            "tpe",
            "cma_es",
            "pso",
            "genetic",
            "differential_evolution",
            "nsga_ii",
        ],
        ...,
    ]
    scheduler: Literal["asha"]
    scheduler_is_resource_only: Literal[True] = True
    trials_per_searcher: int = Field(ge=1)
    timesteps_per_trial: int = Field(ge=1)
    walk_forward_folds: int = Field(ge=2)
    same_search_space: Literal[True] = True
    same_seed_fold_budget: Literal[True] = True
    test_partition_visible_during_search: Literal[False] = False

    @field_validator("searchers")
    @classmethod
    def validate_searchers(
        cls,
        searchers: tuple[
            Literal[
                "default",
                "random",
                "tpe",
                "cma_es",
                "pso",
                "genetic",
                "differential_evolution",
                "nsga_ii",
            ],
            ...,
        ],
    ) -> tuple[
        Literal[
            "default",
            "random",
            "tpe",
            "cma_es",
            "pso",
            "genetic",
            "differential_evolution",
            "nsga_ii",
        ],
        ...,
    ]:
        """Require every core comparison once."""
        if len(searchers) != len(set(searchers)) or set(searchers) != _CORE_HPO:
            raise ValueError("HPO searchers must contain every core method exactly once")
        return searchers


class StatisticsProtocol(FrozenExperimentModel):
    """Multi-seed summaries and inferential-analysis policy."""

    confidence_level: float = Field(ge=0.95, le=0.95)
    dispersion: tuple[Literal["mean", "std", "median", "best", "worst"], ...]
    interval_method: Literal["student_t"]
    paired_test: Literal["wilcoxon_signed_rank"]
    multiple_comparison_correction: Literal["holm"]
    effect_size: Literal["paired_rank_biserial"]
    report_best_seed_only: Literal[False] = False


class ComputeProtocol(FrozenExperimentModel):
    """Bounded local and remote execution resources."""

    seeds: tuple[int, ...]
    cpu_quickcheck_required: Literal[True] = True
    remote_gpu_count: int = Field(ge=1)
    gpu_model: str = Field(min_length=1)
    max_parallel_gpu_trials: int = Field(ge=1)
    ray_optional: Literal[True] = True

    @field_validator("seeds")
    @classmethod
    def validate_seeds(cls, seeds: tuple[int, ...]) -> tuple[int, ...]:
        """Require at least five unique seeds."""
        if len(seeds) < 5:
            raise ValueError("formal experiments require at least five seeds")
        if len(seeds) != len(set(seeds)) or any(seed < 0 for seed in seeds):
            raise ValueError("formal seeds must be unique and non-negative")
        return seeds


class ExperimentGroupProtocol(FrozenExperimentModel):
    """One mandatory Phase 12 experiment group."""

    code: Literal["A", "B", "C", "D", "E", "F"]
    name: str = Field(min_length=1)
    enabled: Literal[True] = True
    methods: tuple[str, ...]
    required_metrics: tuple[str, ...]


class FormalExperimentProtocol(FrozenExperimentModel):
    """Top-level immutable protocol for publication-eligible Phase 12 runs."""

    schema_version: Literal["1.0"]
    protocol_id: Literal[
        "protocol-v1",
        "protocol-v2",
        "protocol-v3",
        "protocol-v4",
    ]
    supersedes_protocol: Literal[
        "protocol-v1",
        "protocol-v2",
        "protocol-v3",
    ] | None = None
    status: Literal["draft", "frozen"]
    purpose: Literal["softwarex_formal_experiments"]
    development_run_inputs_allowed: Literal[False] = False
    software_release: Literal["v1.0.0-rc2"]
    dataset: DatasetProtocol
    fx: FXProtocol
    partitions: PartitionProtocol
    execution: ExecutionProtocol
    drl: DRLProtocol
    agents: AgentProtocol
    hpo: HPOProtocol
    statistics: StatisticsProtocol
    compute: ComputeProtocol
    groups: tuple[ExperimentGroupProtocol, ...]

    @model_validator(mode="after")
    def validate_complete_protocol(self) -> FormalExperimentProtocol:
        """Require Groups A–F and keep the test interval outside FX acquisition gaps."""
        if tuple(group.code for group in self.groups) != ("A", "B", "C", "D", "E", "F"):
            raise ValueError("formal groups must be ordered [A, B, C, D, E, F]")
        experiment = self.dataset.selection.experiment_window
        if self.fx.acquisition_window.start > experiment.start:
            raise ValueError("FX acquisition must start no later than experiment data")
        if self.fx.acquisition_window.end < experiment.end:
            raise ValueError("FX acquisition must cover the experiment window")
        if self.protocol_id in {"protocol-v2", "protocol-v3", "protocol-v4"}:
            expected_parent = {
                "protocol-v2": "protocol-v1",
                "protocol-v3": "protocol-v2",
                "protocol-v4": "protocol-v3",
            }[self.protocol_id]
            if self.supersedes_protocol != expected_parent:
                raise ValueError(
                    f"{self.protocol_id} must identify superseded {expected_parent}"
                )
            cutoff = self.dataset.selection.selection_information_cutoff
            if cutoff is None or cutoff >= self.partitions.test.start:
                raise ValueError("universe selection cutoff must precede the test partition")
            if cutoff >= self.partitions.train.start:
                raise ValueError("formal training must start after universe formation")
        if (
            self.protocol_id in {"protocol-v3", "protocol-v4"}
            and self.agents.prompt_source is None
        ):
            raise ValueError(
                f"{self.protocol_id} must bind an auditable prompt source path"
            )
        return self


class ProtocolVerification(FrozenExperimentModel):
    """Structured freeze/hash/input verification result."""

    protocol_id: str
    protocol_path: str
    checksum_path: str
    protocol_sha256: str = Field(pattern=_SHA256_PATTERN)
    schema_valid: bool
    checksum_valid: bool
    source_inventory_valid: bool
    fx_snapshot_valid: bool
    processed_manifest_present: bool
    processed_manifest_valid: bool
    prompt_source_valid: bool
    is_ready_to_execute: bool
    blockers: tuple[str, ...] = ()
