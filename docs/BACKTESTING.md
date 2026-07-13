# Backtesting

The backtest harness uses the same `TrendAlignedVolatilityExpansion` strategy as live scanning.

Run the deterministic fixture:

```powershell
.venv\Scripts\python.exe -m app.spot.cli backtest:run
```

The fixture validates that a known bullish setup produces a qualified paper-trade plan.

Current MVP limitations:

- The command is a deterministic smoke backtest, not a broad historical walk-forward optimization.
- The design keeps conservative intrabar handling and shared strategy functions.
- Production parameter optimization is not automatic.
