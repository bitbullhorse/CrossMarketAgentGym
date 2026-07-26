# Phase 2 issue checklist

## Scope

- [x] Implement the Gymnasium `CrossMarketPortfolioEnv` reset/step contract.
- [x] Implement the required dictionary observation and `[N+1]` action space.
- [x] Enforce close-`t` signal, open-`t+1` execution, close-`t+1` valuation.
- [x] Add leakage tests proving future close does not change prior observation or execution.
- [x] Implement native, union, intersection, and scheduled-rebalance calendars.
- [x] Separate forward valuation from the authoritative tradable mask.
- [x] Implement latest-on-or-before FX conversion into one base currency.
- [x] Implement raw-action cleaning and long-only/signed normalization.
- [x] Implement `TradableMask`, `LongOnly`, `MaxAssetWeight`, `MaxMarketWeight`,
  `Leverage`, `CashFloor`, and `TurnoverLimit`.
- [x] Implement configurable `LotSize`, `TPlusOne`, `PriceLimit`, and `Suspension` rules.
- [x] Make `ExecutionEngine` the sole account-state mutation boundary.
- [x] Implement explicit transaction costs and slippage.
- [x] Reconcile cash, signed positions, costs, and value on every step.
- [x] Implement all six required reward functions.
- [x] Return full action, constraint, trade, cost, risk, and value audit information.
- [x] Add manual accounting, property, mask, T+1, price-limit, and suspension tests.
- [x] Pass Gymnasium and Stable-Baselines3 environment checks.
- [x] Pass a seeded 1,000-step random-action finite-value smoke test.
- [x] Replace the Phase 2 CLI placeholder with `cmag env check`.
- [x] Add the RL extra to minimal CI installation.
- [x] Pass 89 tests and the 85% branch-coverage gate.
- [x] Pass `ruff check .`.
- [x] Pass `mypy src`.
- [x] Pass `pip check`.
- [x] Pass `python -m uv lock --check`.

## Deferred by phase boundary

- Phase 3 must provide a custom Stable-Baselines3 dictionary feature extractor for `[N,L,F]`;
  using the default image CNN is prohibited.
- Production exchange-calendar and instrument-master inputs must replace observed/static fixture
  sessions before a production backtest.
- Borrow fees, margin calls, exchange-specific tax schedules, and intraday partial-fill simulation
  are not claimed by the daily Phase 2 engine.
- Source anomaly remediation and full private-source canonical conversion remain blocked on the
  research-approved data policy recorded in Phase 1.
