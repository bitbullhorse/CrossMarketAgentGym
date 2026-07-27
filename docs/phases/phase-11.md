# Phase 11 — independent reproduction and usability

Status: **release closing**. Tasks 1–8 pass locally. The workspace owner reports that multiple
independent participants completed review, all modules operated normally, and the P0/P1 audit is
clear. The dedicated Linux CPU/Docker Task B–I workflows and permanent rc2 Release evidence remain
the final machine-verifiable gates. Phase 12 has not started.

## Goal and input validation

This increment closes the gap between artifact-integrity verification and actual repeat execution
of PPO training. The source run must pass its fingerprint, run-manifest, resolved TrainerConfig,
dataset-manifest, checkpoint, train-partition, test-selection, network, and account-state checks
before computational replay can start.

The workspace contained the rc1 contract and a valid `repro-ppo-quickstart` source run. The
workspace owner reported that Phase 11.3 installation, data/environment validation, PPO,
Research Agent, risk committee, PSO, report generation, and artifact persistence checks had
already succeeded. Those statements are retained as input context, not represented as independent
participant evidence.

## Added files

- `src/crossmarket_agentgym/release/reproduction_models.py`: strict tolerance, comparison,
  reproduction-level, and structured-report models.
- `src/crossmarket_agentgym/environments/observations.py`: strict `flat`/`tensor` market-window
  configuration.
- `configs/reproduction/phase11_cpu.yaml`: reviewed absolute/relative tolerances, exact
  invariants, and repeated-run threshold.
- `scripts/compare_reproduced_run.py`: executes replay, verifies the replay manifest, and enforces
  the CPU minimum level.
- `scripts/repro_test_cpu.sh` and `scripts/repro_test_docker.sh`: clean evidence workflow and
  non-root, network-disabled container workflow.
- `reproducibility_tests/`: independent protocol, participant template, issue table, and interim
  report.
- `docs/issues/phase-11-checklist.md`: input, implementation, test, and exit gates.

## Modified files

- `release/reproduction.py`: honest artifact mode, isolated training replay, source immutability,
  checkpoint loading, metric/invariant/artifact comparisons, statistical fallback, audit output,
  and manifest persistence.
- `cli/app.py`: `--verify-only`, the required `--execute --compare` pair,
  `--tolerance-config`, and collision-safe `--replay-run-id`.
- `release/cli_inventory.json`: reviewed additive Phase 11 CLI parameters; frozen Python API and
  current Schema snapshot generated deterministically.
- Environment, RL workflow/evaluation, reporting index, directive fusion, and team aggregation
  code for Tasks 5–8.
- PPO/SAC/TD3/environment configurations, with SB3 quickstarts explicitly using `flat`.
- Reproduction, CLI, quickstart, API, security, README, and design-log documentation.
- Environment, runtime metadata, risk/committee semantics, reproduction, contract, and CLI tests
  plus the offline documentation verifier.

The complete Phase 11 source-controlled file inventory is:

```text
CHANGELOG.md
README.md
.github/workflows/{phase11-linux-cpu.yml,phase11-docker.yml}
configs/
├── env/{cross_market.yaml,sample_cross_market.yaml}
├── reproduction/phase11_cpu.yaml
└── train/{ppo.yaml,ppo_quickstart.yaml,ppo_tune_gpu.yaml,ppo_tune_smoke.yaml,sac.yaml,td3.yaml}
docs/
├── {api-reference.md,cli-reference.md,design-log.md,directive-fusion-contract.md}
├── {environment-contract.md,environment.md,multi_agent.md,quickstart.md}
├── {reproducibility.md,security.md,stable-api.md,training-contract.md}
├── issues/phase-11-checklist.md
└── phases/phase-11.md
release/
├── {api_inventory.csv,cli_inventory.json,config_schema_inventory.csv,format_registry.json}
├── {rc2_checklist.md,release_notes_v1.0.0-rc2.md}
└── {release_blockers.md,known_issues.md,compatibility_matrix.md}
schemas/rc1/
├── checksums.json
├── configs/{environment_check.schema.json,training.schema.json}
└── artifacts/{evaluation_result.schema.json,phase7_summary.schema.json}
    {team_result.schema.json,training_summary.schema.json}
scripts/
├── build_phase11_release_evidence.py
├── compare_reproduced_run.py
├── repro_test_cpu.sh
├── repro_test_docker.sh
├── run_phase11_tasks.py
├── verify_phase11_distribution.py
└── verify_docs.py
src/crossmarket_agentgym/
├── agents/{aggregation/policies.py,directives.py,models.py}
├── cli/app.py
├── environments/{__init__.py,checks.py,observations.py,portfolio.py}
├── evaluation/results.py
├── release/{reproduction.py,reproduction_models.py}
├── reporting/indexer.py
└── rl/{config.py,trainers/sb3.py,workflow.py}
tests/
├── agents/{test_aggregation.py,test_directives.py,test_layer_stack.py}
├── integration/{test_portfolio_environment.py,test_training_workflow.py}
├── release/{test_phase10_contracts.py,test_reproduction.py}
├── release/test_phase11_workflows.py
├── reporting/{test_benchmarks_workflow.py,test_models_indexer.py}
└── unit/{test_baselines.py,test_cli.py,test_policy_extractors.py}
reproducibility_tests/
├── .gitignore
├── issue_summary.csv
├── independent_audit_attestation.md
├── participant_template.md
├── protocol.md
└── reproducibility_report.md
```

## Design decisions

1. The frozen `reproduce_run()` API remains read-only and backward compatible. Artifact
   verification is labeled `artifact_verified`, not full computational reproduction.
2. Training executes only when both `--execute` and `--compare` are supplied. The pair makes
   resource consumption and filesystem writes explicit.
3. Replays are append-only under
   `runs/reproductions/<source-run-id>/<replay-run-id>`. Existing source and replay directories
   cannot be overwritten; failed replay evidence is retained.
4. The execution config copies the source seed, TrainerConfig, split, environment, and execution
   protocol. Only dataset/output paths and replay run ID are relocated. The workflow constructs
   train and validation partitions only.
5. Exact equality is required for timesteps, algorithm, dataset-manifest hash, recorded and
   recomputed TrainerConfig hash, execution protocol, and checkpoint loadability.
6. Five validation metrics use the maximum of the reviewed absolute bound and scaled relative
   bound. At least three compatible invariant-passing replays are required before the statistical
   fallback is available.
7. Bitwise comparison covers checkpoint, validation metrics, trades, and weights. A checkpoint
   archive byte difference prevents a bitwise claim even if every numeric comparison passes.
8. Network use, test-partition access, and external account mutation remain literal false fields
   in the strict report model.
9. Observation layout is an adapter concern: both layouts preserve identical float32 values and
   the raw tensor remains internal. Tensor-mode SB3 training fails closed without a custom
   extractor.
10. Runtime identity and timing live in the training summary; evaluation sample sufficiency lives
    with the metrics rather than being inferred by report consumers.
11. Effective cash reserve is
    `max(max(administrator floor, Agent floor), 1 - effective risk budget)` and its derivation is
    persisted in the directive audit.
12. Committee policy, detected conflict, resolved decision, selected confidence, minimum
    committee confidence, and projection causes are separate fields.

## Tests and current acceptance evidence

The targeted suite exercises artifact-only semantics, tamper detection, actual PPO retraining,
source snapshots, isolated output, five metrics, six invariants, checkpoint loading, manifest
verification, replay-ID collisions, strict tolerance validation, all ordered computational
levels, CLI flag conflicts, and prior Phase 9 Agent/Phase 7 Replay compatibility.

A final direct-CLI run created `replay-repro-ppo-quickstart-003` and reached
`numerically_reproduced`. All five metric differences were zero, all exact invariants passed, and
metrics/trades/weights were byte-identical. The checkpoint ZIP SHA-256 differed, so
`bitwise_reproduced` was correctly not claimed. The source snapshot was unchanged, no test
partition existed, and the replay manifest verified. Three compatible replays also exercised and
passed the statistical comparison; numerical reproduction remained the selected stronger level.

Current local targeted gates:

| Gate | Result |
|---|---|
| Flat environment check | Gymnasium/SB3 passed; 64 steps; no warnings |
| Maximum accounting error | `2.3283064365386963e-10` (required below `1e-8`) |
| Task 5–8 targeted tests | 58 passed |
| Full repository tests | 331 passed |
| Branch coverage | 87.35% (required 85%) |
| Leakage/accounting/risk-boundary selection | 43 passed independently |
| Ruff | passed |
| Strict mypy | passed, 135 source files |
| Frozen contracts | 251 API, 11 config Schemas, 20 artifact Schemas; passed |
| Documentation contract | 25 required documents; passed |
| Phase 11 Workflow/evidence contracts | 6 passed |
| Source/replay artifact-manifest verification | 12 replay artifacts; passed |
| Flat PPO computational replay | numerical; all five metric differences `0.0` |
| Bash syntax | two Phase 11 scripts; passed with Git Bash |
| Linux CPU/Docker execution | pending dedicated GitHub-hosted runs |

## Exit-condition audit

- Tasks 1–4 computational replay: **passed locally**.
- Tasks 5–8 observation/report/audit semantics: **passed locally**.
- CPU replay at least numerical: **passed locally**.
- Artifact integrity, source immutability, no-test, no-network, and no-account-mutation checks:
  **passed locally**.
- Independent functional review: **reported complete by the workspace owner**.
- P0/P1 independent audit: **reported complete with P0 = 0 and P1 = 0**.
- Individual participant details absent from the workspace: **not invented**.
- `v1.0.0-rc2`: **blocked**.
- Phase 12 readiness: **no**.

## Remaining issues

- Run the dedicated GitHub-hosted Linux CPU and Docker Task B–I workflows on the exact candidate
  commit and record both run IDs.
- Attach the deterministic commit-bound evidence ZIP and checksum to the rc2 GitHub Release before
  closing this report.
