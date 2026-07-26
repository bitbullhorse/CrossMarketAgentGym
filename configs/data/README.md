# Data configurations

- `sample.yaml` validates the canonical, manifest-backed synthetic sample.
- `local_stock_data.yaml` reads one source file per market for a quick compatibility check.
- `local_stock_data_full.yaml` audits all supported local CSV/Excel source files.

Validation never deletes rows, sorts input, fills missing prices, or writes to `stock_data/`.
