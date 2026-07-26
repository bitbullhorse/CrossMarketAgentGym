# Phase 8 — reports, run browser, and optional service

## Goal

Deliver a CPU-first, one-command SoftwareX evidence report over existing immutable artifacts.
Provide deterministic Markdown, HTML, tables, figures, a safe run browser, descriptive benchmark
comparison, and an optional local read-only FastAPI service. Preserve the locked-test and
hyperparameter-selection boundary.

## File changes

- `reporting/models.py`, `io.py`: strict report schemas, bounded JSON, finite metrics, contained
  paths, and deterministic hashing.
- `reporting/indexer.py`: whitelist-only Phase 3/4/6/7 run discovery and fingerprints.
- `reporting/benchmarks.py`: recorded return, risk, turnover, cost, seed-variance, and runtime
  comparison with explicit missing values.
- `reporting/charts.py`: dependency-free accessible SVG bar charts with signed zero axes.
- `reporting/workflow.py`: deterministic Markdown, HTML, browser, CSV, JSON, SVG, and manifest
  generation.
- `api/config.py`, `api/app.py`: optional loopback-first read-only FastAPI service and safe report
  asset routing.
- `cli/app.py`: `cmag report softwarex`, `cmag report runs`, and `cmag service run`.
- `configs/reporting/softwarex.yaml`: the six-category SoftwareX declaration over eight existing
  runs.
- `configs/reporting/service.yaml`: local read-only service configuration.
- `examples/serve_reports.py`: optional service entry example.
- `tests/reporting/`, `tests/api/`, `tests/test_cli.py`: schema, indexing, benchmark,
  reproducibility, CLI, route, and security regressions.
- `docs/reporting-service-contract.md`: reporting and service public contract.

## Design decisions

1. Report generation is a read-only consumer and has literal `selection_authority: false`; it
   cannot become an HPO objective or scheduler input.
2. The run index is a bounded whitelist rather than serialized internal models. Prompts,
   credentials, raw configuration, Provider responses, checkpoints, and arbitrary files are not
   public report fields.
3. Missing or statistically underdetermined metrics remain `N/A`. The report does not fill missing
   experiments with zero, infer winners, or claim that planned experiments ran.
4. The default SoftwareX report is validation-descriptive. Locked test artifacts may be rendered
   only after selection and never flow back into tuning.
5. Native SVG is used for the CPU path to avoid adding a large plotting dependency and to make
   deterministic artifact hashing practical.
6. All source, evidence, and output paths remain inside the workspace; generated output may not
   live inside `runs/`.
7. FastAPI/Uvicorn remain optional. The service is local and read-only by default; remote binding
   requires explicit opt-in and does not imply production authentication.
8. Canonical report URLs end in `/` so portable relative assets work both as static files and
   through the service.

## Tests

Phase 8 tests cover all six required experiment declarations, evidence requirements, strict and
finite JSON, path containment, all four run artifact families, deterministic selection order,
duplicate and missing IDs, whitelist secret exclusion, return/risk metrics, cross-seed variance,
missing metrics, manifest reproducibility, signed SVGs, CLI commands, output isolation, service
remote opt-in, route allowlists, security headers, canonical redirects, and secret-free responses.

The generated page was also loaded through the real local service in the in-app Chromium browser.
The canonical redirect resolved correctly, all four SVGs reported 900×460 natural dimensions, and
the report and chart layouts rendered successfully.

## Acceptance result

Phase 8 passed locally on Python 3.12.13:

| Check | Result |
|---|---|
| One-command report | `cmag report softwarex --config configs/reporting/softwarex.yaml` |
| Indexed selected runs | 8 Phase 3/4/6/7 runs |
| Benchmark | 3 validation rows: PPO, SAC, TD3 |
| Experiment matrix | 2 completed, 2 partial, 2 planned |
| Generated tables / figures | 4 CSV / 4 SVG |
| Generated report files | Markdown, HTML, static browser, two JSON payloads, manifest |
| Selection authority | `false` |
| Manifest SHA-256 identity | `71cb3e2d075a69746a3db19cdf0bdcbf11ac9c71f71f8ecc16e6239694996551` |
| Browser acceptance | Canonical redirect and all SVG assets passed |
| Full test suite | 289 passed; 4 existing SB3 observation warnings |
| Branch coverage | 87.71%, above the 85% gate |
| Ruff | Passed |
| Mypy | Passed for 119 source files |

Machine-readable evidence is written to `docs/reporting/phase8-acceptance.json`.

## Open issues

- Cross-stock zero-shot and leave-one-market-out experiments have not been executed. Their report
  rows are deliberately `planned`.
- Market-mechanism and Agent/HPO evidence is sufficient to verify infrastructure but not a
  publication-scale multi-seed ablation matrix; those rows remain `partial`.
- The Phase 3 quickstart evaluation artifacts contain one recorded step per selected run, so
  Sharpe and Sortino correctly remain `N/A`.
- The service has no production authentication or TLS termination. Keep the default loopback
  binding unless an authenticated reverse proxy and deployment policy are supplied.
- GPU, Ray, live-progress streaming, and asynchronous report refresh remain optional extensions
  after the CPU contract.
