# Environment configurations

`cross_market.yaml` validates the sample environment with Gymnasium, optional SB3, 1,000 seeded
random actions, finite-value checks, and per-step accounting reconciliation.

The execution protocol is fixed to `close_signal_next_open`: an observation ends at close `t`, the
target is executed at open `t+1`, and the account is then marked at close `t+1`.
