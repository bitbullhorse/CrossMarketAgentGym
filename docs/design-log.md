# Design log

## DL-0001 — Package naming

- Decision: use distribution `crossmarket-agent-gym`, import package `crossmarket_agentgym`, and
  CLI `cmag`.
- Reason: matches the execution report and avoids import-name hyphens.

## DL-0002 — Supported Python versions

- Decision: support Python 3.11 and 3.12; keep Linux/Python 3.11 as the required CI baseline.
- Reason: the report requires 3.11, while the available local and remote interpreters are 3.12.
  Supporting both is conservative and lets the CPU and GPU probes share package metadata.

## DL-0003 — Dependency groups

- Decision: keep the installable core CPU-oriented. RL, HPO, LLM transport, Ray, and service
  dependencies are explicit extras; CUDA wheels remain an environment concern.
- Reason: this keeps `pip install -e .` and offline imports light while preserving reproducible
  constraint files for each capability.

## DL-0004 — LLM provider and model

- Decision: every project Agent configuration uses an OpenAI-compatible DeepSeek provider and
  exactly `deepseek-v4-pro`. The API key and base URL are named by `DEEPSEEK_API_KEY` and
  `DEEPSEEK_BASE_URL`; no credential value is stored.
- Reason: explicit user requirement and report security boundary.

## DL-0005 — Search versus scheduling

- Decision: `tuning.searchers` and `tuning.schedulers` are separate packages and future protocols.
  ASHA, HyperBand, and PBT will only implement the scheduler protocol.
- Reason: prevents resource allocation from being reported as a search algorithm.

## DL-0006 — Account mutation boundary

- Decision: Agent packages may emit immutable, schema-validated directives only. Environment
  execution and accounting code will be the sole account-state mutation boundary.
- Reason: an LLM must never bypass deterministic risk rules.

## DL-0007 — Dataset and test visibility

- Decision: raw `stock_data/` is local-only. Every split will carry a partition capability; HPO and
  Agent tools receive train/validation capabilities but never a test capability.
- Reason: structural enforcement is safer than relying on caller convention.

## DL-0008 — Phase 0 data observation

- Decision: defer all normalization to Phase 1 and do not silently reshape the source tree.
- Observation: the local source contains 978 paths and approximately 414.6 MB. HK/JP/US use flat
  CSV files; CN uses a nested layout and therefore needs a dedicated adapter.
- Reason: adapters must report anomalies instead of mutating source data.

## DL-0009 — Remote authentication

- Decision: do not place the supplied SSH password in a command line, temporary script, repository
  file, or captured log. Attempt key-only non-interactive authentication first.
- Result: the host was reachable but rejected key authentication. Remote provisioning remains
  pending until a key or non-logged secret channel is available.

## DL-0010 — Mixed legacy input boundary

- Decision: support RESSET `.xls`/`.xlsx` only in the CN source adapter; canonical storage remains
  CSV/Parquet.
- Reason: the actual A-share source is nested Excel while the other markets are flat CSV. Keeping
  this exception at ingestion prevents Excel assumptions from reaching environments.

## DL-0011 — Local trading dates

- Decision: parse the first ISO date component of timezone-bearing source timestamps.
- Reason: converting local midnight to UTC can move HK/JP rows to the previous calendar date.

## DL-0012 — Adjustment semantics

- Decision: preserve raw OHLC as `adjusted=false`; map RESSET `AdjClpr2` and Yahoo `Adj Close` only
  to the separate `adjusted_close` field.
- Reason: the source does not provide enough provenance to claim all OHLC fields share a single
  adjustment convention.

## DL-0013 — Unknown exchange metadata

- Decision: use `US_UNSPECIFIED` for US legacy CSV records.
- Reason: filename and ticker alone cannot reliably distinguish NYSE, Nasdaq, and other venues.

## DL-0014 — Redistributable sample

- Decision: generate deterministic synthetic data instead of copying private input rows.
- Reason: redistribution rights for RESSET/Yahoo-derived inputs are not assumed.

## DL-0015 — Source anomalies

- Decision: fail the quality status while retaining all source rows and exact issue locations.
- Evidence: all 978 files and 2,036,819 rows were readable, but the full audit found missing or
  non-numeric bars, invalid OHLC envelopes, and date-order violations.
- Reason: explicit invalidity is safer than an undocumented repair.

## DL-0016 — Daily execution protocol

- Decision: a close-`t` observation produces an action that executes at open `t+1` and is marked at
  close `t+1`.
- Reason: this is the most conservative daily-bar protocol and prevents same-close execution.

## DL-0017 — Calendar and tradability separation

- Decision: default to an observed union calendar, provide explicit native/intersection/scheduled
  composition, and forward-fill only valuation prices.
- Reason: an exchange closure must never become tradable because another market is open.

## DL-0018 — FX as-of boundary

- Decision: convert local prices using the latest FX rate on or before each session and fail when no
  historical rate exists.
- Reason: backward filling would leak a future conversion rate into the account.

## DL-0019 — Constraint infeasibility

- Decision: freeze non-tradable positions and report any resulting cap violation as unresolved.
- Reason: inventing a trade to make a target appear feasible would violate the execution mask.

## DL-0020 — Accounting mutation boundary

- Decision: `AccountState` is frozen and `ExecutionEngine` is the only component that replaces it.
- Reason: policies and later LLM Agents must not bypass deterministic account and risk controls.

## DL-0021 — Costs and reconciliation

- Decision: record fees and slippage separately and reconcile open-price mid-value before marking at
  close.
- Reason: this makes missing cash, double-counted costs, and sign errors fail immediately.

## DL-0022 — T+1 and market parameters

- Decision: retain sellable long shares as session state; markets and lot sizes are configuration
  inputs rather than universal constants.
- Reason: market rules change and must be replayed from run configuration.

## DL-0023 — SB3 market tensor adapter

- Decision: preserve the required `[N,L,F]` observation and require a custom dictionary feature
  extractor in Phase 3.
- Reason: flattening the environment contract merely to suppress the generic SB3 image heuristic
  would discard useful structure.

## DL-0024 — Partition capabilities

- Decision: every training/evaluation environment carries an immutable train, validation, test, or
  smoke capability; the Trainer accepts train only.
- Reason: data authority must be enforced by structure rather than caller naming conventions.

## DL-0025 — Isolated partition panels

- Decision: copy a bounded `MarketDataPanel` for each partition and do not construct test during
  training.
- Reason: an environment that merely stops early could still expose future arrays through internal
  attributes.

## DL-0026 — Unified SB3 trainer

- Decision: PPO, SAC, TD3, and optional A2C share one Trainer, artifact, callback, and evaluation
  contract.
- Reason: algorithm choice must not change auditability or partition safety.

## DL-0027 — Policy families

- Decision: provide flat MLP, parameter-shared asset MLP, and Transformer extractors while keeping
  IR-MoE optional.
- Reason: the report requires multiple viable policies and prohibits making IR-MoE the only path.

## DL-0028 — Checkpoint provenance

- Decision: record the config and dataset hashes, seed, requested/actual timesteps, and dependency
  versions beside every final checkpoint.
- Reason: model weights without their data and runtime identity are not reproducible artifacts.

## DL-0029 — Locked test evaluation

- Decision: training writes validation results only; test evaluation is a separate write-once
  command.
- Reason: test results must not influence model selection or be repeatedly overwritten after
  peeking.

## DL-0030 — Feature scaling

- Decision: built-in extractors use stateless signed-log compression; any fitted standardizer
  requires a train capability and freezes before validation/test transforms.
- Reason: this keeps CPU quickstarts stable without fitting normalization statistics on future
  partitions.

## DL-0031 — Search and scheduling boundary

- Decision: define separate `SearchAlgorithm` and `TrialScheduler` protocols and registries.
- Reason: ASHA, HyperBand, and PBT allocate resources; treating them as candidate generators would
  make configuration ambiguous and prevent independent composition.

## DL-0032 — Search-space expression safety

- Decision: interpret conditions and constraints with a restricted hand-written AST evaluator.
- Reason: even a builtins-free `eval` violates the repository architecture guard and creates an
  unnecessary executable-string boundary.

## DL-0033 — Local study persistence

- Decision: use SQLite WAL storage and strict JSON component checkpoints for the CPU executor.
- Reason: standard-library persistence is portable, inspectable, crash-tolerant, and does not
  require Ray or a service merely to resume a local experiment.

## DL-0034 — Validation-only robust objective

- Decision: optimize median validation Sharpe after explicit drawdown, turnover, and cross-seed
  instability penalties; support a mixed-direction Pareto tuple separately.
- Reason: a lucky seed or high-turnover return must not dominate selection, and the test set must
  remain unavailable until parameters are locked.

## DL-0035 — CPU optimizer reference

- Decision: implement the nine required searchers with NumPy behind one normalized mixed-space
  contract.
- Reason: CPU quickstart and deterministic tests must not depend on GPU, Ray, or a third-party HPO
  service; optional adapters can be added without changing public semantics.

## DL-0036 — Terminal versus intermediate scheduling

- Decision: keep the scheduler API capable of intermediate stop/promote/exploit decisions while
  the first local PPO executor reports terminal resource only.
- Reason: this establishes the independent scheduler contract now; live cancellation and
  distributed PBT checkpoint transfer require a later incremental/Ray executor and must not delay
  the reproducible CPU path.

## DL-0037 — Provider credential ownership

- Decision: only `OpenAICompatibleProvider` reads an API key value, and only from the configured
  process environment variable.
- Reason: Pydantic configuration, YAML, request hashes, object reprs, and audit artifacts must
  remain safe to share.

## DL-0038 — Exact structured output

- Decision: accept only a JSON object that validates against the requested Pydantic model.
- Reason: extracting a plausible object from surrounding prose hides model failures and could turn
  unvalidated text into an instruction.

## DL-0039 — Administrator fallback

- Decision: Provider/schema failure returns a prevalidated static fallback supplied outside the
  model.
- Reason: asking the failing model to invent its own fallback does not create a safety boundary.

## DL-0040 — Python-only tool registry

- Decision: Agent tools are pre-registered typed Python callables; user text cannot reach a shell
  or subprocess adapter.
- Reason: schema validation cannot make arbitrary shell text safe, and later Agents must operate
  through narrow auditable capabilities.

## DL-0041 — Strict Replay identity

- Decision: Replay matches the SHA-256 of messages, response schema, tool definitions, and
  generation settings in exact sequence.
- Reason: returning a response from a merely similar request would create a convincing but
  irreproducible experiment.

## DL-0042 — Redaction timing

- Decision: recursively redact immediately before tool output, audit, and Replay persistence while
  preserving public environment-variable names and token counts.
- Reason: redaction at display time leaves unsafe artifacts on disk; indiscriminate field-name
  matching would also destroy useful non-secret provenance.

## DL-0043 — Single and multi-Agent identity

- Decision: represent a single Agent as a one-instance `TeamSpec` executed by `AgentRuntime`.
- Reason: separate single/team paths would drift in Provider, tool, audit, timeout, and safety
  behavior.

## DL-0044 — Structured topology edges

- Decision: every topology edge carries a validated `UpstreamDecision`; conflict policies inspect
  decision enums and typed constraints, never arbitrary prose.
- Reason: free-text voting is ambiguous and could convert unvalidated language into authority.

## DL-0045 — Independent count expansion

- Decision: expand count before construction and give each instance a stable ID, SHA-256-derived
  seed, Provider, messages, budgets, retries, timeout, audit, and Replay state.
- Reason: sharing mutable Provider or budget state would make committee votes order-dependent and
  defeat reproducibility.

## DL-0046 — Deterministic parallelism

- Decision: CPU threads may execute independent roles concurrently, but results and audit events
  are emitted in configuration order.
- Reason: parallel completion order is nondeterministic and must not alter arbitration or Replay
  identity.

## DL-0047 — Partial failure and quorum

- Decision: isolate Provider fallback, plugin exception, retry exhaustion, and timeout per
  instance; resolve only when configured quorum remains.
- Reason: one unavailable reviewer should not crash a large committee, while silently lowering the
  required participation would weaken governance.

## DL-0048 — Conservative runtime fallback

- Decision: a failed risk role denies new positions and proposes full cash/zero exposure; lack of
  quorum also returns a static rejection.
- Reason: an LLM outage must not relax risk. Phase 7 will still intersect advice with immutable
  administrator hard limits before deterministic projection.

## DL-0049 — Layer teams share AgentRuntime

- Decision: Research, Risk, and Hierarchical layers each configure a `TeamSpec`, including a
  one-instance team, and execute through the Phase 6 `AgentRuntime`.
- Reason: layer-specific execution paths would reopen Provider, topology, timeout, tool, audit,
  and arbitration inconsistencies already closed by the unified runtime.

## DL-0050 — Administrator intersection is final authority

- Decision: Risk and Hierarchical directives may only narrow immutable environment limits; maxima
  use minimum, floors use maximum, and permissions use logical AND.
- Reason: an LLM must never convert confidence or committee consensus into authority to expand
  the deterministic feasible set.

## DL-0051 — Constraint fusion before conditioning

- Decision: Phase 7 implements hierarchical `constraint` fusion and rejects other fusion modes.
- Reason: conditioning changes observations, policies, checkpoints, and compatibility tests;
  deterministic projection delivers the safety value without destabilizing those contracts.

## DL-0052 — Zero-Provider no-LLM boundary

- Decision: `no_llm` disables every layer before runtime construction and projects only under
  administrator constraints.
- Reason: disabling LLM functionality must remove credential, network, Provider, and inference
  dependencies rather than merely ignore an already-created client.

## DL-0053 — Conservative low-frequency reuse

- Decision: a layer that is not due reuses a previously validated directive, otherwise a static
  fallback, and makes no Provider call.
- Reason: deterministic cadence must not depend on wall-clock timing or silently increase model
  interaction frequency.

## DL-0054 — Directive Replay recomputes policy

- Decision: persist typed proposals and administrator configuration, then recompute risk merge,
  hierarchy fusion, and projection during Replay.
- Reason: replaying only final weights would not prove that hard limits and no-new-position logic
  were applied.

## DL-0055 — Research budget and test boundary

- Decision: expose validation-only evaluation/comparison to Research Agents and require a
  successful compute estimate before expensive training or tuning.
- Reason: orchestration convenience cannot authorize unbudgeted work or leak the locked test set
  into model or hyperparameter selection.

## DL-0056 — Whitelist-only run index

- Decision: index only selected finite scalars and provenance from recognized Phase 3/4/6/7
  summaries.
- Reason: serializing internal run objects would expose prompts, credentials, configuration,
  checkpoints, or schema drift through a supposedly read-only browser.

## DL-0057 — Reporting has no selection authority

- Decision: every benchmark comparison carries literal `selection_authority: false` and is not a
  tuning objective or scheduler input.
- Reason: a convenient report must not create a second path for test metrics or visual ranking to
  influence hyperparameter selection.

## DL-0058 — Missing evidence remains missing

- Decision: render unavailable or underdetermined metrics as `N/A` and require evidence before an
  experiment can be declared complete.
- Reason: replacing missing evidence with zero, a derived rank, or a polished narrative would make
  incomplete experiments appear executed.

## DL-0059 — Deterministic native SVG

- Decision: generate accessible SVG charts directly for the CPU report path and use a signed zero
  axis.
- Reason: this avoids a heavy plotting dependency, preserves negative values visually, and makes
  repeatable artifact hashing practical.

## DL-0060 — Hashed report identity

- Decision: hash the resolved configuration, declared evidence, whitelisted source index, and
  every generated artifact in a deterministic manifest.
- Reason: report filenames alone do not prove which runs or evidence produced a published figure.

## DL-0061 — Optional local read-only service

- Decision: keep FastAPI/Uvicorn optional, bind to loopback by default, require remote opt-in, and
  expose only run metadata plus whitelisted generated report assets.
- Reason: browsing reports does not require write authority or arbitrary filesystem access, while
  production authentication and TLS are deployment concerns that must not be silently implied.

## DL-0062 — Single-source stable version

- Decision: release `0.1.0` and obtain package metadata dynamically from
  `crossmarket_agentgym/_version.py`; require `CITATION.cff` and `.zenodo.json` to match it.
- Reason: duplicated executable and distribution versions can silently create archives that do
  not correspond to their tag or citation.

## DL-0063 — Offline resources and optional dependencies

- Decision: place the synthetic four-market sample and reference configuration inside the wheel,
  resolve them through `importlib.resources`, and lazily load online Provider, RL, Ray, and service
  dependencies.
- Reason: an installed core wheel must run its CPU quickstart without a source checkout, network
  call, API credential, or heavyweight optional stack.

## DL-0064 — Read-only reproduction levels

- Decision: reproduce recorded runs by verifying provenance and deterministic artifacts rather
  than silently retraining. Recompute Agent request identity and Phase 7 directive projection
  where exact replay material exists; verify immutable hashes and archives for training/tuning.
- Reason: retraining can consume unbounded resources and need not be bitwise deterministic across
  hardware, while provenance verification is bounded, auditable, and honest about its level.

## DL-0065 — External publication boundary

- Decision: local and CI release gates may build, inspect, and archive artifacts, but PyPI,
  GitHub Release, tag push, and Zenodo deposition require an explicit authorized tag or workflow
  dispatch. Do not invent a DOI before Zenodo returns one.
- Reason: irreversible publication and identifier claims are external state changes, not implied
  by preparing a release.

## DL-0066 — Bounded non-root container

- Decision: build the wheel in a separate Docker stage, copy only the wheelhouse into the runtime
  stage, exclude private/local artifacts from the context, and run as UID 10001.
- Reason: a release image does not need source credentials, raw data, test outputs, build tools, or
  root authority.

## DL-0067 — Distributed execution remains a third abstraction

- Decision: add `TrialBatchExecutor` with local and optional Ray implementations. Ray controls
  placement only; searchers still generate candidates and ASHA/HyperBand/PBT remain independent
  schedulers. Restore results to suggestion order.
- Reason: distributed completion order and resource placement must not change optimizer history or
  collapse search, scheduling, and execution into one component.

## DL-0068 — Canonical cross-platform configuration identity

- Decision: write resolved Agent configuration with LF line endings and verify legacy Windows
  artifacts by parsing, redacting, and canonically serializing YAML before hashing.
- Reason: CRLF conversion is not a semantic configuration change and must not invalidate an
  otherwise exact replay.

## DL-0069 — Distribution content verification

- Decision: accept exactly one wheel and one source archive, inspect both without extraction,
  require packaged quickstart resources and release materials, and reject forbidden path
  components.
- Reason: `twine check` validates metadata rendering but does not prove that an archive is usable
  offline or free of local data, credentials, runs, environments, and checkpoints.

## DL-0070 — Artifact verification is not computational reproduction

- Decision: retain the frozen `reproduce_run()` artifact-verification API and describe its level
  as `artifact_verified`. Require the explicit CLI pair `--execute --compare` before any training
  is rerun.
- Reason: hashes establish provenance and integrity but cannot establish that the computation can
  be repeated. Explicit execution also prevents a historically bounded command from unexpectedly
  consuming training resources.

## DL-0071 — Immutable isolated replay directories

- Decision: store every training replay below
  `runs/reproductions/<source-run-id>/<new-replay-run-id>`, snapshot every source file before
  execution, reject an existing replay ID, and retain failed replay directories.
- Reason: reproducibility evidence must not overwrite the run being tested or erase failures.

## DL-0072 — Ordered reproduction levels and reviewed tolerances

- Decision: classify results as `artifact_verified`, `bitwise_reproduced`,
  `numerically_reproduced`, `statistically_reproduced`, or `failed`. Compare five validation
  metrics with reviewed absolute/relative tolerances and require exact timesteps, algorithm,
  dataset hash, TrainerConfig hash, execution protocol, and checkpoint loadability. CPU
  quickstart requires at least numerical reproduction.
- Reason: SB3 checkpoint archives may differ byte-for-byte while loaded policies and evaluated
  results remain numerically identical. A single Boolean cannot express that distinction or a
  controlled repeated-run statistical fallback.

## DL-0073 — Explicit financial-tensor observation layout

- Decision: preserve `[N,L,F]` internally, expose configurable `flat` and `tensor` layouts, use
  `flat` for packaged PPO/SAC SB3 quickstarts, and require a custom `BaseFeaturesExtractor` for
  `tensor`.
- Reason: SB3's Box heuristic treats a three-dimensional float tensor as an image. Flattening the
  adapter view removes false image requirements without changing OHLCV dtype, scale, ordering, or
  information content.

## DL-0074 — Runtime and sample sufficiency are first-class evidence

- Decision: persist wall, training, and evaluation durations plus runtime identity in every
  training summary; persist evaluation episode/sample counts and warnings when dispersion has
  fewer than two samples.
- Reason: a null runtime and an unqualified `std_return: 0.0` obscure whether a run executed and
  whether its reported dispersion has statistical meaning.

## DL-0075 — Cash floor proves its risk-budget derivation

- Decision: compute
  `max(administrator/Agent cash floor, 1 - effective risk budget)` and journal both inputs,
  effective output, `max` operator, and invariant reason.
- Reason: a stricter effective cash floor can otherwise look like an unexplained Agent override;
  the derivation proves that invested capital cannot exceed the deterministic risk budget.

## DL-0076 — Separate committee configuration, conflict, and outcome

- Decision: record configured conflict policy, detected conflict, aggregate decision, selected
  directive confidence, minimum committee confidence, and dominant/secondary projection reasons
  as distinct fields.
- Reason: fields such as `policy: reject` and `decision: approve` conflate arbitration rules with
  outcomes and make safe projection causes ambiguous during review.

## DL-0077 — Phase 11 evidence executes the built artifact

- Decision: the Linux CPU gate builds a wheel from the tested commit, attests that exact wheel,
  installs it into a new virtual environment, and executes Tasks B–I with CUDA unavailable.
- Reason: an editable checkout can pass while the published wheel is missing configs, sample data,
  or Provider code; provenance must bind the tested bytes to the source workflow.

## DL-0078 — Docker reproduction is offline and resource bounded

- Decision: rebuild with `--pull --no-cache`, expose packaged configs/sample data inside the
  non-root runtime image, and execute Tasks B–I under `--network none`, 2 CPU, 7 GB memory, and
  disabled CUDA visibility.
- Reason: container reproduction should demonstrate a bounded CPU artifact rather than depend on
  host files, runtime downloads, GPU availability, or unrestricted resources.

## DL-0079 — Workflow artifacts are staging, not archival evidence

- Decision: both workflows emit the same `11_3_task_summary` schema plus logs, runs, identities,
  and SHA-256 records. After both pass on the tag commit, combine them deterministically and attach
  the bundle plus checksum to the GitHub Release.
- Reason: ordinary Actions artifacts expire, while a Release asset provides a stable,
  commit-bound evidence source for later audit.

## DL-0080 — Record independent clearance without inventing participants

- Decision: accept the release operator's statement that multiple independent participants
  completed review and P0/P1 are zero, while explicitly declining to fabricate names,
  environments, scores, or participant files absent from the workspace.
- Reason: the reported clearance is a legitimate release input, but provenance requires a clear
  distinction between supplied attestation and machine-generated evidence.

## DL-0081 — Formal source selection is quality-gated and outcome-independent

- Decision: inventory all 978 source files, reject every source with a remaining OHLCV quality
  error, and select a fixed per-market universe using a salted SHA-256 of market and symbol.
- Reason: selecting on return, volatility, benchmark membership, or test-period performance would
  leak outcomes. Hash order is deterministic and performance-agnostic.

## DL-0082 — Exclude only auditable non-OHLCV records

- Decision: allow one semantic projection before quality validation: a source row may be excluded
  only when open, high, low, close, and volume are all missing. Record every excluded source
  index. Do not impute, sort, deduplicate, repair, or partially drop invalid bars.
- Reason: RESSET workbooks contain financial-report observations alongside daily-price fields.
  Treating an all-empty price record as a zero-price bar is incorrect, while silently repairing
  partial bars would make the formal dataset irreproducible.

## DL-0083 — Formal FX is an immutable offline input

- Decision: acquire one official ECB EXR csvdata response before protocol freeze, record its
  exact bytes and SHA-256, derive local-currency-to-USD rates as
  `USD-per-EUR / currency-per-EUR`, and use latest-on-or-before lookup.
- Reason: a live API may revise history or be unavailable. The snapshot makes formal runs
  network-independent and prevents future-rate lookup.

## DL-0084 — Safety constraints dominate ablation completeness

- Decision: Group D never disables the deterministic risk boundary. The closest permitted
  comparison is named `minimum_deterministic_risk_projection` and retains hard leverage,
  non-negative cash, and account-mutation invariants.
- Reason: the project-wide safety contract forbids LLM or experiment code from bypassing the
  deterministic risk layer. A paper ablation cannot weaken a release-blocking invariant.

## DL-0085 — Protocol v1 is write-once

- Decision: bind protocol v1 to the source inventory, ECB snapshot, processed dataset manifest,
  rc2 software release, prompt source, partitions, budgets, methods, seeds, and statistics with
  SHA-256 `428386c42ef89110b88014a8f3c87ffdddc48810e16d6991d1ee3f74f2789cae`.
  Any semantic change requires protocol v2 rather than overwrite.
- Reason: post-result protocol edits permit undisclosed researcher degrees of freedom and break
  run-to-paper traceability.

## DL-0086 — Future source availability is a blocking universe leak

- Decision: block and supersede protocol-v1 before freezing a formal matrix because its
  full-window coverage rule observed whether a source remained available through the locked test
  period. Preserve its protocol and input hashes, publish a structured supersession notice, and
  accept no v1 development run as a formal result.
- Reason: performance-independent selection can still leak future information when eligibility
  depends on future listing or data availability. Survivorship disclosure does not make that
  selection valid for a no-future-universe protocol.

## DL-0087 — Form the fixed universe before training and censor later failures

- Decision: protocol-v2 forms the universe at `2021-02-01`, begins training at `2021-02-02`,
  and uses only cutoff-visible coverage, cutoff-visible quality, and salted symbol hashes for
  selection. A selected source with a later quality error retains its symbol identity and becomes
  unavailable from the first invalid observation; no repair, replacement, or reselection occurs.
- Reason: fixed membership avoids future-informed substitution. Prefix censoring is conservative,
  reproducible, and preserves the economic meaning of an unavailable asset without fabricating
  prices or allowing later data quality to change the original stock pool.

## DL-0088 — A Prompt hash requires a versioned source path

- Decision: block protocol-v2 before matrix freeze because its Prompt SHA-256 had no resolvable
  source artifact. Protocol-v3 binds `experiments/agents/prompt_bundle_v1.json`, verifies its
  hash during every preflight, and injects its exact role strings into formal Agent specs.
- Reason: a hash without retrievable bytes cannot be independently reproduced. Binding the
  system prompts and deterministic user-message serialization contract prevents undocumented
  Prompt drift while the matrix commit binds the runtime renderer implementation.

## DL-0089 — Global sequence failures cannot use physical prefix censoring

- Decision: block protocol-v3 after its real-data CPU gate showed that a globally unsorted source
  could begin with a later chronological block. Protocol-v4 keeps the fixed symbol but retains
  only its already validated formation-window observations when the future audit reports an
  ordering or duplicate-key error. Local bad-bar errors continue to use first-invalid-row prefix
  censoring.
- Reason: physical position is a safe causal boundary for a local row defect only when sequence
  order itself is valid. For a global ordering failure, the formation window is the last
  chronology-independent set known to be valid without sorting, repairing, or using future data.

## DL-0090 — Formal training boundaries remain private to Phase 12

- Decision: implement the frozen first-outcome date through a Phase 12-private environment and
  training adapter. Keep the rc2 `TemporalSplitConfig`, `MarketDataPanel`, and exported HPO
  constructor contracts unchanged. Group B, Group C, locked HPO retraining, and every
  walk-forward fold use the private adapter.
- Reason: the experiment protocol needs an exact `2021-02-02` first training execution, but an
  experiment implementation must not mutate the already frozen release API or Schema. The
  frozen-contract gate now proves both requirements simultaneously.
