# Phase 8 issue checklist

## Reporting schemas and indexing

- [x] Re-read the detailed report's Phase 8 scope and SoftwareX experiment matrix.
- [x] Define strict schemas for runs, experiments, benchmark rows, manifests, and build summaries.
- [x] Require all six SoftwareX experiment categories.
- [x] Require evidence for completed experiments and preserve planned/partial states.
- [x] Index Phase 3 training, Phase 4 tuning, Phase 6 Agent, and Phase 7 layer artifacts.
- [x] Use a bounded metadata whitelist; exclude raw messages, credentials, checkpoints, and
  arbitrary files.
- [x] Reject path escapes, non-finite JSON, duplicate IDs, missing selected runs, and oversized
  inputs.
- [x] Keep report output outside the immutable runs tree.

## Tables, figures, and benchmark semantics

- [x] Generate Markdown and HTML reports with one CPU command.
- [x] Generate a static run browser, JSON payloads, and four CSV tables.
- [x] Generate four deterministic, accessible SVG figures without a plotting dependency.
- [x] Render signed values around a true zero axis.
- [x] Compare return, risk, cost, turnover, seed variance, and runtime only from recorded evidence.
- [x] Leave underdetermined metrics as `N/A`.
- [x] Mark every comparison as descriptive with no hyperparameter-selection authority.
- [x] Avoid fabricating cross-stock, leave-one-market-out, or publication-scale ablation results.
- [x] Hash configuration, evidence, source index, and every generated artifact.
- [x] Verify repeat generation produces the same manifest.

## Optional service and security

- [x] Keep FastAPI and Uvicorn in an optional `service` dependency group.
- [x] Default to loopback binding, disabled API docs, and explicit remote opt-in.
- [x] Expose only read-only health, run-index, report-index, report, and safe-asset routes.
- [x] Expose no arbitrary run-file or mutation endpoint.
- [x] Add CSP, MIME-sniffing, and referrer security headers.
- [x] Canonicalize report URLs so relative SVG assets load correctly.
- [x] Verify the rendered report and all four SVGs in a real browser session.

## Acceptance

- [x] Add reporting, service, CLI, path, provenance, and reproducibility tests.
- [x] Run the real SoftwareX report command over the selected Phase 3/4/6/7 artifacts.
- [x] Record eight indexed runs, three algorithm rows, four tables, and four figures.
- [x] Run the full unit suite with the branch-coverage gate.
- [x] Run Ruff and strict Mypy.
- [x] Update CI, README, contracts, security notes, design log, and changelog.
- [x] Record machine-readable acceptance evidence.

## Deferred by phase boundary

- [ ] Execute dedicated cross-stock zero-shot experiments.
- [ ] Execute leave-one-market-out experiments.
- [ ] Execute publication-scale market-mechanism and Agent/HPO ablation matrices with multiple
  seeds.
- [ ] Add authenticated remote deployment, database-backed pagination, and asynchronous live
  monitoring if required by a later deployment phase.
- [ ] Add GPU/Ray reporting adapters only after the CPU artifact contract remains stable.
