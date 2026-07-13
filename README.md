# Nexora DeFi

Solana Spot Momentum and Trade Intelligence Engine for paper trading only.

The active runtime is an alert-only, paper-trading-only Solana engine. It dynamically builds a liquid token universe, stores OHLCV candles, evaluates one deterministic strategy, sends qualified paper-trade plans to Telegram when enabled, records virtual positions, and exposes diagnostics for no-signal days.

Forbidden by design: live orders, auto-buying, auto-selling, swap execution, wallet signing, private-key handling, seed-phrase handling, futures, margin, leverage, and short selling.

## Stack

- Python 3.12
- FastAPI
- SQLAlchemy async ORM
- Alembic migrations
- APScheduler jobs
- SQLite locally, Postgres-compatible `DATABASE_URL` in deployment

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest
```

## Run

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Render/Railway start command:

```powershell
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Key Endpoints

- `GET /health`
- `GET /ready`
- `GET /integrations/health`
- `GET /spot/status?live=true`
- `POST /spot/universe/build`
- `POST /spot/market/refresh`
- `POST /spot/scan`
- `POST /spot/telegram/test`

## CLI Diagnostics

```powershell
.venv\Scripts\python.exe -m app.spot.cli system:status --live
.venv\Scripts\python.exe -m app.spot.cli providers:check
.venv\Scripts\python.exe -m app.spot.cli universe:build
.venv\Scripts\python.exe -m app.spot.cli universe:show --tier CORE
.venv\Scripts\python.exe -m app.spot.cli market:validate --token=<mint>
.venv\Scripts\python.exe -m app.spot.cli scan:once
.venv\Scripts\python.exe -m app.spot.cli scan:funnel
.venv\Scripts\python.exe -m app.spot.cli signals:recent
.venv\Scripts\python.exe -m app.spot.cli paper:positions
.venv\Scripts\python.exe -m app.spot.cli paper:trades
.venv\Scripts\python.exe -m app.spot.cli backtest:run
.venv\Scripts\python.exe -m app.spot.cli telegram:test
.venv\Scripts\python.exe -m app.spot.cli database:check
```

## Required Production Variables

- `DATABASE_URL`
- `DEXSCREENER_ENABLED=true`
- `GECKOTERMINAL_ENABLED=true`
- `PAPER_TRADING_ENABLED=true`
- `LIVE_TRADING_ENABLED=false`
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` when `TELEGRAM_SIGNALS_ENABLED=true`

See [docs/CONFIGURATION.md](C:/Users/HP/Documents/NEXORA-DEFI/docs/CONFIGURATION.md) and [docs/APIS.md](C:/Users/HP/Documents/NEXORA-DEFI/docs/APIS.md).

## Strategy

Only one strategy is implemented: Trend-Aligned Volatility Expansion.

It requires:

- 4h Solana/token regime not bearish or data-insufficient
- 1h bullish EMA alignment
- 15m consolidation
- confirmed closed-candle breakout
- volume above baseline
- structural plus ATR stop
- dynamic targets
- minimum reward/risk and quality score

Details: [docs/STRATEGY.md](C:/Users/HP/Documents/NEXORA-DEFI/docs/STRATEGY.md).

## Current Readiness Meaning

The app never reports paper-observation readiness when required market data, database, candle history, or Telegram notification capability is missing. A no-signal day is inspected through `scan:funnel`, `universe:show`, `signals:recent`, and provider checks.

## Documentation

- [Architecture](C:/Users/HP/Documents/NEXORA-DEFI/docs/ARCHITECTURE.md)
- [Strategy](C:/Users/HP/Documents/NEXORA-DEFI/docs/STRATEGY.md)
- [APIs](C:/Users/HP/Documents/NEXORA-DEFI/docs/APIS.md)
- [Configuration](C:/Users/HP/Documents/NEXORA-DEFI/docs/CONFIGURATION.md)
- [Debugging](C:/Users/HP/Documents/NEXORA-DEFI/docs/DEBUGGING.md)
- [Backtesting](C:/Users/HP/Documents/NEXORA-DEFI/docs/BACKTESTING.md)
- [Paper Trading](C:/Users/HP/Documents/NEXORA-DEFI/docs/PAPER_TRADING.md)
- [Operations](C:/Users/HP/Documents/NEXORA-DEFI/docs/OPERATIONS.md)
- [Known Limitations](C:/Users/HP/Documents/NEXORA-DEFI/docs/KNOWN_LIMITATIONS.md)
- [API Requirements Report](C:/Users/HP/Documents/NEXORA-DEFI/docs/API_REQUIREMENTS_REPORT.md)
