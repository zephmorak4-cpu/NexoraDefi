# Strategy

The engine implements one strategy: Trend-Aligned Volatility Expansion.

## Inputs

- 4h closed candles for regime.
- 1h closed candles for trend.
- 15m closed candles for setup trigger.
- Token liquidity, volume, market-cap, pool, and source metadata.

## Rules

1. Reject malformed, future, non-closed, or impossible candles.
2. Classify regime with EMA alignment.
3. Block longs when regime is `BEARISH` or `DATA_INSUFFICIENT`.
4. Require 1h close above fast EMA and fast EMA above slow EMA.
5. Detect a 15m consolidation range using swing high/low.
6. Require the trigger candle to close above the consolidation high.
7. Require trigger volume above baseline volume by `SIGNAL_VOLUME_MULTIPLIER`.
8. Build an entry zone from breakout close and ATR fraction.
9. Select the lower of structural stop and ATR-buffer stop.
10. Reject stops that are too wide or too tight.
11. Build targets from configured R multiples.
12. Require minimum reward/risk and quality score.
13. Persist a fingerprint so the same setup is not resent.

## Determinism

OpenAI is not used to decide entries, stops, targets, reward/risk, quality, or signals. It may only explain an already validated structured plan when enabled.
