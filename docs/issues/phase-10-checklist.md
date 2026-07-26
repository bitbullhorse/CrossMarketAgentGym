# Phase 10 issue checklist — `v1.0.0-rc1` freeze

This checklist starts Phase 10. An unchecked item is not accepted evidence. Phase 10 is not
complete until every exit criterion is checked and a completion report identifies the exact
commit and release-candidate artifacts.

## Input preconditions

- [x] Phase 0–9 local acceptance reports are present.
- [x] CPU quickstart has passed on the packaged CN/HK/JP/US sample.
- [x] PPO, SAC, and TD3 training/evaluation evidence is present.
- [x] Research, Risk, and Hierarchical layers can be enabled independently.
- [x] Single-Agent and multi-Agent configurations use `AgentRuntime`.
- [x] The CPU HPO study can run and resume without test-set access.
- [x] Leakage, accounting, risk-boundary, unit, integration, property, and Replay tests passed at
  the Phase 9 baseline.
- [x] The current CLI starts and exposes the Phase 0–9 command groups.
- [ ] Establish an immutable Git baseline commit; the repository currently has no commit history.
- [ ] Record a reachable source repository and CI run for the baseline.
- [ ] Revalidate the baseline on Python 3.11/Linux in addition to Python 3.12/Windows.

## Release blockers

- [ ] Resolve every P0/P1 item in `release/known_issues.md`.
- [ ] Change the Python distribution version from `0.1.0` to PEP 440 `1.0.0rc1`.
- [ ] Map PEP 440 `1.0.0rc1` to the required Git/Release tag `v1.0.0-rc1`.
- [ ] Mark the GitHub Release as a prerelease and prevent it from being presented as v1.0.0.
- [ ] Make release readiness accept the intended rc1 channel without accepting arbitrary
  development versions.
- [ ] Align `CITATION.cff`, Zenodo metadata, release notes, wheel metadata, and release manifest.
- [ ] Replace the sample Manifest's stale `software_version: 0.1.0.dev0`.
- [ ] Define and verify one rc1 mapping for software, data Manifest, protocol, benchmark, and paper
  status without claiming Phase 12/13 artifacts already exist.
- [ ] Execute the Docker build/quickstart gate on a Docker-capable host.
- [ ] Confirm no security, accounting, information-leakage, or nondeterministic-test blocker exists.

## Public API freeze

- [ ] Generate `release/api_inventory.csv` from the actual importable objects.
- [ ] Classify every exported object as stable, provisional, experimental, or internal.
- [ ] Reduce or explicitly classify the current 232 `__all__` export records.
- [ ] Resolve documentation references that are not exported from the documented namespace.
- [ ] Give every stable API a public doc page, signature, behavior, exceptions, and version-added
  declaration.
- [ ] Add a compatibility test that fails on an unreviewed removal, rename, signature change, or
  stability-class change.
- [ ] Define deprecation warnings, minimum support window, and removal process.
- [ ] Define Semantic Versioning and release-candidate rules.

## CLI freeze

- [ ] Inventory root options, command groups, leaf commands, arguments, exit codes, and optional
  dependency behavior.
- [ ] Freeze the current root commands: `train`, `evaluate`, `tune`, `quickstart`, and `reproduce`.
- [ ] Freeze the `data validate`, `env check`, `agent run`, `agent provider-check`,
  `report softwarex`, `report runs`, `service run`, and `release check|manifest|verify` commands.
- [ ] Add or reconcile the Phase 11-required `cmag report --run-id <RUN_ID>` interface.
- [ ] Add the exact Phase 11 quickstart configuration names or version the reproduction protocol
  to an equivalent tested command set.
- [ ] Snapshot CLI help and fail on unreviewed command/option removals or renames.
- [ ] Document stable exit-code semantics and missing-extra errors.

## Configuration and artifact Schema freeze

- [ ] Inventory and export canonical JSON Schema for project, data, environment, training,
  Provider, AgentRuntime, three-layer Agent, tuning, reporting, and service root configurations.
- [ ] Remove platform-dependent JSON Schema generation and current non-serializable `Path` default
  warnings.
- [ ] Add deterministic schema hashes and a verification command.
- [ ] Freeze the canonical OHLCV and Dataset Manifest formats.
- [ ] Freeze the training/evaluation run-directory layout and add a versioned run manifest.
- [ ] Freeze Agent message, tool-call, response, Replay, team-result, and directive formats.
- [ ] Freeze audit JSON/JSONL envelopes with explicit schema versions.
- [ ] Freeze HPO Trial/Study/checkpoint formats and version the SQLite schema with migrations.
- [ ] Keep parsers compatible with existing Phase 3/4/6/7 artifacts or provide explicit migration
  fixtures.
- [ ] Reject unknown fields and incompatible major schema versions.
- [ ] Add golden fixtures and tamper/hash tests for every frozen format.

## Dependency and environment freeze

- [ ] Review core dependencies and remove anything not needed by the installed CPU quickstart.
- [ ] Keep RL, HPO, online LLM transport, Ray, service, release, and development capabilities in
  explicit extras.
- [ ] Make the documented Phase 11 `.[dev]` installation sufficient for its CPU reproduction
  tasks, or freeze and document one corrected install command before rc1.
- [ ] Export a complete CPU lock that cannot resolve CUDA packages.
- [ ] Probe the target GPU driver securely before choosing a CUDA/PyTorch build.
- [ ] Generate complete `constraints-cpu.txt` and `constraints-gpu.txt`.
- [ ] Generate `environment-cpu.yml` and `environment-gpu.yml`.
- [ ] Record tested and untested Python/PyTorch/Gymnasium/SB3/Optuna/Ray combinations in
  `release/compatibility_matrix.md`.
- [ ] Verify there are no unpinned Git URL dependencies.
- [ ] Install every supported extra independently and verify lazy optional imports.
- [ ] Run `pip check` and lock consistency checks in clean environments.

## Code and repository cleanup

- [ ] Classify broad exception handlers as audited failure boundaries or replace them.
- [ ] Remove or justify the environment render-mode `print`.
- [ ] Confirm examples are the only remaining intentional direct `print` calls.
- [ ] Search for TODO/FIXME/HACK, debugger calls, temporary paths, example credentials, and
  author-machine-only paths.
- [ ] Separate release blockers from future enhancements.
- [ ] Verify all stable public callables/classes have usable docstrings.
- [ ] Verify raw data, runs, reports, caches, credentials, checkpoints, and local environments
  remain outside release archives.

## Required documentation

- [ ] Add `docs/api_stability.md`.
- [ ] Add `docs/versioning_policy.md`.
- [ ] Add `docs/deprecation_policy.md`.
- [ ] Add `docs/installation.md`.
- [ ] Add `docs/quickstart.md`.
- [ ] Add `docs/data_schema.md`.
- [ ] Add `docs/environment.md`.
- [ ] Add `docs/market_rules.md`.
- [ ] Add `docs/rl_training.md`.
- [ ] Add `docs/llm_agents.md`.
- [ ] Add `docs/multi_agent.md`.
- [ ] Add `docs/tuning.md`.
- [ ] Add `docs/reproducibility.md`.
- [ ] Add `docs/troubleshooting.md`.
- [x] Maintain `docs/security.md`.
- [ ] Add `docs/faq.md`.
- [ ] Test links, fenced commands, configuration paths, package names, and documented imports.
- [ ] Update README and all Phase 0–9 references for the rc1 lifecycle.

## Required release files

- [ ] Add `release/rc1_checklist.md`.
- [ ] Add `release/api_inventory.csv`.
- [ ] Add `release/known_issues.md`.
- [ ] Add `release/compatibility_matrix.md`.
- [ ] Add `release/release_notes_v1.0.0-rc1.md`.
- [ ] Record schema/format inventories and hashes in the release candidate.
- [ ] Record the exact commit, source date epoch, wheel/sdist hashes, and clean-environment
  evidence.

## Automation

- [ ] Add `scripts/build_release.sh`.
- [ ] Add `scripts/verify_release.sh`.
- [ ] Add `scripts/create_clean_env_test.sh`.
- [ ] Put cross-platform logic in typed Python helpers and keep shell wrappers minimal.
- [ ] Add API inventory export/verify automation.
- [ ] Add config/artifact Schema export/verify automation.
- [ ] Add documentation link/command verification automation.
- [ ] Add deterministic double-build comparison.
- [ ] Add clean wheel installation and source-tree-independent quickstart.
- [ ] Add CI Docker build and unprivileged-container quickstart.
- [ ] Ensure every publication workflow has a non-publishing dry-run path.

## Tests

- [ ] Run the full unit suite and the 85% branch-coverage gate.
- [ ] Run property tests, including accounting invariants and frozen-schema rejection.
- [ ] Run all leakage tests and explicitly confirm HPO has no test capability.
- [ ] Run CPU integration tests for data, environment, PPO/SAC/TD3, Agents, HPO resume, reports,
  and reproduction.
- [ ] Run LLM Mock and exact Replay tests; do not require an online key.
- [ ] Run wheel install tests in clean Python 3.11 and 3.12 environments.
- [ ] Run Docker build and Docker quickstart tests.
- [ ] Run CLI smoke/help/exit-code snapshot tests.
- [ ] Run documentation command and link tests.
- [ ] Verify current Phase 3/4/6/7 artifacts remain readable after schema versioning.
- [ ] Run Ruff, strict Mypy, dependency checks, lock checks, archive checks, and credential scans.
- [ ] Verify two rc1 builds from the same commit and epoch have identical hashes.

## Phase 10 exit criteria

- [ ] Every stable API is documented.
- [ ] Release blocker count is zero.
- [ ] A clean environment installs the rc1 wheel.
- [ ] CPU quickstart succeeds from the installed wheel.
- [ ] Docker quickstart succeeds as an unprivileged user.
- [ ] Configuration and artifact Schemas are frozen and hashed.
- [ ] Locks and compatibility matrix are complete.
- [ ] All required tests pass without random failure.
- [ ] `v1.0.0-rc1` can be created from one immutable commit.
- [ ] Release notes and known issues are complete.
- [ ] `docs/phases/phase-10.md` records all files, decisions, tests, deviations, blockers, and
  evidence.
- [ ] Phase 11 readiness is explicitly approved; no third-party reproduction has been skipped.

## Phase 11 preparation only

- [ ] Prepare, but do not fabricate, participant protocol/templates and comparison automation.
- [ ] Do not publish rc2 until real independent participants finish and P0/P1 are zero.
- [ ] Do not start formal Phase 12 experiments from development or rc1 smoke runs.
