# Environment

`CrossMarketPortfolioEnv` is the deterministic Gymnasium portfolio environment. Signals observed
after close at index `t` execute at the next eligible market open. Actions are desired weights,
but a deterministic projector applies administrator limits before the accounting engine sees
them.

Validate the packaged environment:

```bash
cmag env check --config configs/env/sample_cross_market.yaml
```

The command checks Gymnasium compatibility, Stable-Baselines3 when installed, finite observations
and rewards, accounting identities, and seeded random actions. The packaged SB3 quickstart uses
`observation.market_window_layout: flat`, so OHLCV values remain `float32` financial data while
the `[N,L,F]` window is exposed as a one-dimensional Box. The `tensor` layout remains available
for Transformer, IR-MoE, and other custom feature extractors. See
[environment contract](environment-contract.md) for the exact observation/action spaces,
execution protocol, audit fields, and tolerances.

An LLM can propose a typed directive. It cannot call `step`, place a trade, mutate cash or
positions, or weaken administrator constraints. Deterministic projection is always downstream of
the Agent layer.
