# Data licensing and redistribution

CrossMarketAgentGym source code is licensed under Apache-2.0. That license does not grant rights
to third-party financial data.

The files under `data/sample/` are deterministic synthetic fixtures created for this project and
may be redistributed with the software under Apache-2.0. They are not observations from a real
exchange and must not be represented as investment evidence.

The formal Phase 12 OHLCV and FX payloads are not redistributed. The public release contains only
the acquisition description, Schema, instrument universe, date ranges, quality decisions and
cryptographic hashes required to identify the research inputs. Users must obtain any real market
data under terms granted by the original provider.

`benchmarks/v1/dataset_manifest.json` is metadata, not the underlying dataset. The release archive
must exclude `stock_data/`, `data/processed/`, runs and other restricted payloads.
