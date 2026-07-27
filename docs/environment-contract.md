# Environment and accounting contract

This contract defines the deterministic boundary used by `CrossMarketPortfolioEnv`. Agent and RL
code may propose actions, but only the constraint projector and execution engine can turn them into
account state.

## Timing

For a state observed after local-market close on session `t`:

1. `market_window` contains rows no later than close `t`.
2. The action is cleaned and projected against the next execution session's deterministic rules.
3. Eligible orders execute at open `t+1`.
4. Holdings are marked at close `t+1`.
5. The returned observation ends at close `t+1`.

Changing close `t+1` cannot change the observation at `t`, the projected target, or executed
quantity. It may only change the subsequent mark-to-market value and reward.

## Calendar and currency

- Native calendars expose actual sessions through `MarketCalendar`.
- `CompositeMarketCalendar` supports `native`, `union`, `intersection`, and
  `scheduled_rebalance`.
- The default multi-market panel uses the observed union calendar.
- Forward-filled prices are valuation-only; an unobserved or suspended session always has
  `tradable_mask=false`.
- Local prices enter account arithmetic only after conversion to the configured base currency.
- FX lookup is latest-on-or-before the session. A future rate is never used and a missing
  historical rate fails panel construction.

## Observation and action

The observation is a Gymnasium `spaces.Dict` containing:

| Field | Shape | Meaning |
|---|---:|---|
| `market_window` | `[N×L×F]` or `[N,L,F]` | Per-asset feature history ending at the current close |
| `portfolio_weights` | `[N+1]` | Cash followed by signed asset weights |
| `cash_ratio` | `[1]` | Current base-currency cash weight |
| `tradable_mask` | `[N]` | Current-session execution eligibility |
| `market_ids` | `[N]` | Stable CN/HK/JP/US identifiers |
| `currency_ids` | `[N]` | Stable CNY/HKD/JPY/USD identifiers |
| `risk_state` | `[4]` | Drawdown, rolling volatility, gross exposure, turnover |
| `time_features` | `[4]` | Cyclical weekday and month encoding |

`observation.market_window_layout` controls only the public observation layout:

- `flat` reshapes `[N,L,F]` to `[N×L×F]` in C order and is the default for the packaged
  PPO/SAC SB3 quickstarts;
- `tensor` exposes `[N,L,F]` and requires an explicitly configured custom
  `BaseFeaturesExtractor` for SB3.

Both modes retain `float32` OHLCV semantics. Values are never converted to `uint8` or scaled to
`[0,255]`, and the environment retains the original tensor internally. `cmag env check` captures
SB3 warnings. A tensor image-heuristic warning is represented as the accepted structured warning
`SB3_BOX_IMAGE_HEURISTIC`; any unexpected warning is blocking.

Actions have shape `[N+1]`, with cash first. The deterministic pipeline is:

```text
raw action
→ NaN/Inf cleaning
→ long-only normalization or signed normalization
→ tradable-position freeze
→ long-only / per-asset / per-market / leverage / cash constraints
→ turnover constraint
→ lot, T+1, suspension, price-limit and cash execution rules
→ account replacement
```

If a pre-existing, non-tradable position already violates a cap, the projector freezes it and
records an unresolved constraint. It never invents a prohibited trade merely to make the target
look feasible.

## Accounting identity

All prices below are already in the base currency. At the next open:

```text
pretrade_value = cash + shares · open
post_trade_mid_value = pretrade_value - fees - slippage_cost
end_value = post_trade_cash + post_trade_shares · close
```

Fees and slippage are non-negative. Each execution checks the second identity within
`accounting_tolerance × max(1, pretrade_value)` before replacing `AccountState`; failure raises
`AccountingInvariantError`.

`ExecutionEngine` is the sole account mutation boundary. LLM output, Agent tools, policies, and
callbacks cannot directly write cash or positions.

## Audit output

Every step returns raw, normalized, and projected actions; clipping and unresolved reasons;
execution mask; quantities and order rejection reasons; trade value; fees; slippage; turnover;
portfolio value; drawdown; accounting error; and market exposure.

## DRL adapter note

Gymnasium and Stable-Baselines3 validation pass without image warnings for the packaged flat
quickstart. Tensor policies use the project feature-extractor registry; the default CNN policy is
not an approved adapter for financial tensors.
