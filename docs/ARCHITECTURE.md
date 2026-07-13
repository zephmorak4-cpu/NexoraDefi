# Architecture

Nexora now runs a Solana-only spot momentum engine in paper-trading mode.

## Runtime Flow

```text
provider capability audit
  -> dynamic Solana token discovery
  -> eligibility and ranking
  -> CORE/CANDIDATE/EXCLUDED universe persistence
  -> OHLCV candle refresh
  -> deterministic strategy scan
  -> trade-plan persistence
  -> Telegram alert, if enabled and configured
  -> paper position creation
  -> paper monitoring and performance diagnostics
```

## Main Modules

- `app/spot/providers.py`: provider capability matrix and readiness audit.
- `app/spot/market_data.py`: normalized DexScreener and GeckoTerminal market data.
- `app/spot/universe.py`: hard filters, ranking, tiers, exclusion reasons.
- `app/spot/strategy.py`: one strategy, deterministic indicators, stops, targets, quality score.
- `app/spot/paper.py`: virtual position creation and conservative fill logic.
- `app/spot/repositories.py`: database persistence and diagnostics.
- `app/spot/engine.py`: universe build, candle refresh, scan orchestration.
- `app/spot/cli.py`: production diagnostics.
- `app/spot/api.py`: HTTP operations.

## Database

Alembic migration `27b4a6f95a10_add_spot_momentum_engine.py` creates provider health, universe, candle, evaluation, signal, paper account, paper position, fill, and daily performance tables.

## Safety Boundary

No module signs transactions or submits orders. Jupiter is available only as a quote provider. The code stores simulated paper positions only.
