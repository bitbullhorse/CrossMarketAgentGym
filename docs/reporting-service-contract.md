# Reporting and read-only service contract

Phase 8 turns existing run artifacts into descriptive SoftwareX evidence. Reporting is a
consumer of immutable artifacts; it is not a training, tuning, test-selection, or account-control
surface.

## One-command report

```bash
cmag report softwarex --config configs/reporting/softwarex.yaml
```

The command generates a deterministic report directory containing:

- `report.md` and `report.html`;
- `runs.html`, a static run inventory;
- `report_data.json` and `run_index.json`;
- four CSV tables under `tables/`;
- four dependency-free, accessible SVG figures under `figures/`;
- `manifest.json` with configuration, evidence, source-index, artifact hashes, and sizes.

The report configuration must declare exactly the six SoftwareX experiment categories. A
`completed` category must cite existing evidence. Planned or partial work remains visibly marked;
the renderer never substitutes synthetic measurements for missing experiments or metrics.

## Run index boundary

The indexer recognizes only these versioned artifact families:

- Phase 3 training summaries and validation/test metric summaries;
- Phase 4 tuning summaries and study reports;
- Phase 6 team summaries;
- Phase 7 layer-stack summaries.

Extraction is whitelist-based and bounded by configured run-count and JSON-size limits. The
public index contains identifiers, status, algorithms, partitions, finite scalar metrics, selected
non-secret attributes, artifact counts, source paths, warnings, and SHA-256 fingerprints. It does
not expose raw configurations, prompts, messages, credentials, checkpoints, arbitrary files, or
Provider responses.

All configured and discovered paths are resolved inside the workspace. Report output is prohibited
inside the runs directory. Duplicate identifiers, missing explicitly selected runs, non-finite
JSON, oversized inputs, and path escapes fail closed.

## Comparison semantics

Benchmark tables are descriptive and always carry `selection_authority: false`. The default
configuration reads validation artifacts. A locked test report can be requested only as a
post-selection evaluation view; it is never available to search objectives or schedulers.

Return, drawdown, Calmar, CVaR, turnover, cost, runtime, and cross-seed variance are computed only
from recorded evidence. Sharpe and Sortino remain `N/A` when there are too few observations.
Cross-seed variance remains `N/A` without distinct seeds. No zero, ranking, or winner is invented
for missing evidence.

## Optional FastAPI browser

Install the optional extra and start the local service:

```bash
python -m pip install -e ".[service]"
cmag service run --config configs/reporting/service.yaml
```

The default binds to `127.0.0.1`, disables OpenAPI documentation, and exposes only:

- `GET /health`;
- `GET /api/runs` and `GET /api/runs/{run_id}`;
- `GET /api/reports`;
- `GET /reports/{report_id}/`;
- whitelisted `.csv`, `.json`, `.md`, and `.svg` report assets.

The no-trailing-slash report URL redirects to the canonical trailing-slash URL so relative assets
resolve correctly. The service has no mutation endpoint and no arbitrary run-file endpoint.
Non-loopback binding requires explicit `allow_remote: true`; network authentication and TLS remain
the operator's responsibility and are not implied by that opt-in.

## Reproducibility

Rows, artifacts, and JSON keys have deterministic ordering. JSON rejects NaN and infinity. Native
SVG avoids plotting-library and GPU variance. Rebuilding from the same indexed artifacts,
configuration, and evidence produces the same manifest. Source changes are visible through the
source-index hash even when run directory names remain unchanged.
