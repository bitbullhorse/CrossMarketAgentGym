# Phase 1 data contract

## Canonical key and columns

The primary key is `(trade_date, symbol, market)`. Every daily row requires:

```text
trade_date, symbol, market, exchange,
open, high, low, close, volume,
currency, timezone, adjusted, source
```

Optional columns are:

```text
adjusted_close, turnover, suspension_flag,
limit_up, limit_down, tradable
```

Rows must have finite non-negative OHLCV values, `high` and `low` must envelope open/close, dates
must be non-decreasing within a market-symbol series, keys must be unique, and market metadata must
match:

| Market | Currency | Timezone | Conservative exchange default |
|---|---|---|---|
| CN | CNY | Asia/Shanghai | prefix-derived XSHG/XSHE/XBSE, otherwise CN_UNSPECIFIED |
| HK | HKD | Asia/Hong_Kong | XHKG |
| JP | JPY | Asia/Tokyo | XTKS |
| US | USD | America/New_York | US_UNSPECIFIED |

`US_UNSPECIFIED` is deliberate because the legacy files do not contain exchange metadata.

## Source normalization

- HK/JP/US: flat Yahoo-style CSV.
- CN: nested RESSET `.xls`/`.xlsx`; columns are matched by stable English suffix so both unit-label
  variants load.
- Local timestamp date prefixes are retained. Midnight in Tokyo or Hong Kong is not converted
  through UTC because that can shift the trading date backward.
- Source feature columns such as moving averages and MACD are excluded from the canonical data
  contract; leakage-safe features are recomputed in later phases.
- RESSET `AdjClpr2` is retained as `adjusted_close`, while OHLC remains explicitly unadjusted.

## Quality behavior

Validation accumulates issues and positional examples. It does not drop rows, reorder dates, fill
missing values, infer suspension flags, repair price envelopes, or rewrite source files.

## Manifest behavior

Each canonical artifact records a root-relative path, role, format, SHA-256, byte size, row count,
market/symbol scope, and date bounds. Verification rejects root traversal and recomputes bytes
without modifying the manifest.
