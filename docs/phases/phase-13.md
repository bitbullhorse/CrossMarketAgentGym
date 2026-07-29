# Phase 13 — benchmark-v1 freeze

Status: **complete; Phase 14 ready**.

## Goal and input validation

Phase 13 freezes only the 215 Phase 12 matrix-v6 formal runs. It binds protocol-v4, Dataset
Manifest v3, the formal run matrix and code commit `6f03d3d...`. Phase 12's owner-confirmed
external audit is accepted as an input, but its body, identity and signature are not invented
or stored.

## Added files

- `src/crossmarket_agentgym/benchmarking/{core.py,models.py,render.py}`
- `benchmarks/v1/`
- `paper/generated/benchmark-v1/`
- `scripts/run_phase13_acceptance.py`
- `experiments/review/phase13_benchmark_review.template.md`
- `tests/benchmarking/test_phase13_benchmark.py`
- `tests/integration/test_phase13_cli.py`
- `tests/leakage/test_phase13_benchmark_isolation.py`
- `tests/reproduction/test_phase13_benchmark_freeze.py`
- `docs/issues/phase-13-checklist.md`
- `docs/experiments/phase13-machine-acceptance.json`
- `docs/benchmark-v1.md`
- `docs/phases/phase-13.md`

## Modified files

- `src/crossmarket_agentgym/cli/app.py`
- `release/cli_inventory.json`
- `pyproject.toml`
- `README.md`
- `docs/design-log.md`
- Phase 12 closure state and report files

## Design decisions

- The Benchmark builder never overwrites an existing destination.
- The full formal result root remains the canonical store for approximately 230 GB of trades,
  weights, checkpoints and models. Benchmark v1 freezes each omitted payload by run ID, path,
  byte size and SHA-256.
- Compact metrics, statistics, 100 Agent Replay/directive files and all 40 HPO study reports
  are embedded directly.
- Every table is emitted in four formats. Every SVG has machine-readable source data and a
  source map.
- A generated Benchmark that fails any post-build check is discarded before becoming
  `benchmarks/v1`.
- Reviewer-requested experiments must use a new protocol and a new Benchmark revision; v1 is
  never edited.

## Automation

```bash
cmag benchmark build \
  --protocol experiments/protocol_v4.yaml \
  --source-root results/phase12-review-v1 \
  --visual-payload-root results/phase12-visual-payloads \
  --output benchmarks/v1

cmag benchmark verify --benchmark benchmarks/v1
cmag paper export-tables --benchmark benchmarks/v1
cmag paper export-figures --benchmark benchmarks/v1

python scripts/run_phase13_acceptance.py \
  --benchmark benchmarks/v1 \
  --output docs/experiments/phase13-machine-acceptance.json
```

## Tests and acceptance

The machine gate verifies the required directory tree, 233 files, all SHA-256 values, 215
run/config bindings, 40 HPO isolation records, 100 Agent log records, failure explanations,
all table/figure sources, and the hash-verified representative PPO series used for training,
equity/drawdown and realized market-exposure figures. Unit, integration, leakage and
reproduction suites cover build,
tamper rejection, CLI behavior, HPO partition isolation and deterministic re-verification.

Final results on Python 3.12:

- unit plus Benchmark subset: 95 passed before the final payload test was added;
- integration: 18 passed;
- leakage: 16 passed;
- dedicated Phase 13 reproduction: 1 passed;
- full repository: 403 passed, 85.23% branch-aware coverage;
- Ruff: passed;
- strict mypy: 158 source files passed;
- documentation contract: 25 required files passed;
- frozen contracts: 251 Python API records, 11 config Schemas and 20 artifact Schemas passed.

The final Benchmark verification reports eight passing checks. All 233 files are read-only.
The formal representative series contains 450 training points and 970 locked-test
equity/drawdown points; four realized market exposures are derived from the same 80-asset
weight vectors.

## Review and next-phase readiness

On 2026-07-29 the project owner confirmed that the required non-author Benchmark review passed,
approved Benchmark v1, and reported P0/P1 equal to zero. The review body, reviewer identity and
signature are not stored; none were generated automatically. The disposition is recorded in
`docs/experiments/phase13-machine-acceptance.json`. All Phase 13 exit criteria pass and Phase 14
is ready.
