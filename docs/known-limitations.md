# Known limitations

- Tensor-layout observations require a custom feature extractor. Packaged SB3 quickstarts use
  the flat layout.
- The formal OHLCV dataset cannot be redistributed. The release contains its frozen manifest
  and a synthetic sample, not restricted market records.
- Daily simulation does not reproduce an intraday order book, live latency, taxes, borrow
  availability, or guaranteed execution.
- Online LLM responses can change at the provider. Mock and Replay providers are used by
  deterministic release gates.
- Benchmark results are research evidence, not investment advice or a profitability guarantee.

Security, accounting, information leakage, installation, and deterministic replay defects are
release blockers rather than accepted limitations.
