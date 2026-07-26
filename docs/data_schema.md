# Data schema and manifest

Canonical daily OHLCV rows are stored as Parquet and contain:

| Field | Meaning |
|---|---|
| `timestamp` | Exchange-session date/time in the recorded timezone |
| `market` | One of `CN`, `HK`, `JP`, `US` |
| `symbol` | Stable asset identifier |
| `open`, `high`, `low`, `close` | Adjusted or unadjusted prices declared by the manifest |
| `volume` | Non-negative traded volume |
| `currency` | Quote currency |
| `tradable` | Whether the asset can execute on the row |

The canonical details, validation rules, and legacy-adapter behavior are defined in
[data contract](data-contract.md). `dataset_manifest.json` records schema/software versions,
partitions, row counts, source provenance, and SHA-256 digests. A digest mismatch is blocking.

Validation is read-only:

```bash
cmag data validate --config configs/data/sample.yaml
```

Time splits preserve order. Normalizers fit on training data only; validation is available for
selection; test data is unavailable to HPO and early stopping.
