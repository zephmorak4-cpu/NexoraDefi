# Known Limitations

- Final readiness is not `READY_FOR_PAPER_OBSERVATION` until live universe build produces CORE tokens, candle history exists, Telegram is configured when alerts are enabled, and scans run.
- The established universe depends on broad provider market search and ranked-pool pagination; provider rate limits can still reduce candle completeness.
- Broad historical walk-forward optimization is scaffolded as a deterministic backtest smoke test, not a full optimizer.
- Paper monitoring currently supports initial waiting/open/close state diagnostics; richer partial exits and daily digest text can be expanded from persisted positions.
- Discord mirroring remains optional and not part of readiness.
- OpenAI explanations are optional and disabled by default.
- No live trading, wallet signing, swaps, or order execution exist.
