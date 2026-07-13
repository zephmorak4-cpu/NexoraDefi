# Operations

## Deployment

Render and Railway can use:

```text
Build: pip install -e .
Start: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health: /health
```

## Daily Checklist

```powershell
.venv\Scripts\python.exe -m app.spot.cli providers:check
.venv\Scripts\python.exe -m app.spot.cli universe:build
.venv\Scripts\python.exe -m app.spot.cli universe:show --tier CORE
.venv\Scripts\python.exe -m app.spot.cli scan:once
.venv\Scripts\python.exe -m app.spot.cli scan:funnel
```

## Scheduled Jobs

When paper trading is enabled and live trading is disabled, the scheduler registers:

- `spot_build_universe`
- `spot_refresh_market_data`
- `spot_scan_setups`
- `spot_monitor_paper_trades`
- `spot_provider_health`
- `spot_daily_performance`

## Restart Safety

Run migrations before the app starts. Signals, fingerprints, universe snapshots, candles, and paper positions persist in the database.
