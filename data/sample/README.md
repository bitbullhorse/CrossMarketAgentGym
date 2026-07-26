# Public sample data

This directory contains a deterministic, synthetic, manifest-backed four-market fixture:

- 5 daily rows each for CN, HK, JP, and US;
- 20 total OHLCV rows;
- 4 instrument records;
- 20 local-currency-to-USD FX fixture rows;
- SHA-256, byte size, row count, market, symbol, date range, schema, adjustment rule, and
  provenance in `dataset_manifest.json`.

The sample is for tests and examples, not investment use. It is synthetic because the
redistribution rights of the private `stock_data/` inputs are not assumed. Regenerate it with
`crossmarket_agentgym.data.sample.generate_sample_dataset`.
