# Phase 1 — Data and manifests

## Goal

Normalize all four source-market layouts through one canonical daily OHLCV contract, report data
problems without silent repair, provide CSV/Parquet I/O, make dataset hashes reproducible, and ship
a small redistributable four-market sample.

## File changes

- `data/schemas/ohlcv.py`: immutable row schema and market metadata.
- `data/adapters/`: common adapter result, Yahoo CSV adapter, RESSET Excel adapter, and deterministic
  discovery.
- `data/quality/`: serializable issue/report models and vectorized checks.
- `data/io.py`: canonical CSV/Parquet load and write boundary.
- `data/manifests/`: manifest models, SHA-256 builder, JSON serialization, and verification.
- `data/config.py`, `data/dataset.py`: strict CLI configuration and dataset-wide validation.
- `data/sample.py`, `data/sample/`: deterministic sample generator and generated artifacts.
- `configs/data/`: sample, bounded local smoke, and full local audit configurations.
- `tests/`: schema, adapter, I/O, manifest, property, leakage, real-source, sample, and CLI tests.

## Design decisions

1. Raw source rows are never sorted, filled, dropped, or overwritten.
2. CN codes come from their directory names to preserve leading zeros.
3. RESSET fields use stable English suffix matching across year-specific Chinese unit labels.
4. Local date prefixes are parsed without UTC conversion.
5. US exchange remains `US_UNSPECIFIED`; exchange membership is not guessed.
6. RESSET `AdjClpr2` is retained separately; raw OHLC is marked unadjusted.
7. The public sample is synthetic because source redistribution rights are not assumed.
8. Full private-source Parquet conversion is blocked on an explicit anomaly policy.

## Tests

The suite covers row Schema boundaries, vectorized quality accumulation, no silent row deletion,
CSV/Parquet round trips, Manifest recomputation and tamper detection, source layout discovery,
mixed Excel/CSV loading, local-date preservation, exclusion of source feature columns, deterministic
sample generation, actual four-market source smoke loading, and `cmag data validate`.

## Acceptance result

Phase 1 passed the required local quality gates on Python 3.12.13:

| Check | Result |
|---|---|
| `cmag data validate --config configs/data/sample.yaml` | Passed |
| Four-market sample | CN/HK/JP/US, 4 files, 20 OHLCV rows |
| Manifest verification | All SHA-256 and byte-size checks passed |
| Actual source smoke | 4/4 markets and 8,687 rows loaded |
| Actual source full audit | 978/978 files and 2,036,819 rows loaded; 0 adapter errors |
| `pytest` | 55 passed |
| Branch coverage | 91.97%, above the 85% gate |
| `ruff check .` | Passed |
| `mypy src` | Passed for 48 source files |
| `pip check` | No broken requirements |
| `uv lock --check` | Passed; 111 packages resolved |

Data acceptance details:

- Synthetic sample: 4 markets, 4 OHLCV files, 20 rows, valid Manifest and hashes.
- Bounded local smoke: 4 markets, 4 files, 8,687 rows loaded; source anomalies explicitly reported.
- Full local audit: 978 files and 2,036,819 rows loaded with zero adapter errors.
- Full source quality result: invalid, with 1,800 aggregated findings retained in
  `docs/data/phase1-source-audit-summary.json`.

## Open issues

- Source anomalies require a documented, research-approved policy before canonical full conversion.
- Exchange master data is needed to replace `US_UNSPECIFIED`.
- Trading calendars, corporate-action policy, and production FX inputs are Phase 2 dependencies.
- Linux/Python 3.11 CI and remote GPU validation remain infrastructure follow-ups.
