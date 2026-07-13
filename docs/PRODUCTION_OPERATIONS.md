# Production Operations

## Health

- `/health/live`: process liveness only, fast and cheap.
- `/health/ready`: database, universe, scheduler, Telegram and provider readiness.
- `/health/details`: sanitized operational detail, no secrets.

## Manual Commands

```powershell
.venv\Scripts\python.exe -m app.spot.cli providers:check
.venv\Scripts\python.exe -m app.spot.cli legacy:audit
.venv\Scripts\python.exe -m app.spot.cli runtime:jobs
.venv\Scripts\python.exe -m app.spot.cli universe:build
.venv\Scripts\python.exe -m app.spot.cli universe:show --tier CORE
.venv\Scripts\python.exe -m app.spot.cli scan:once
.venv\Scripts\python.exe -m app.spot.cli telegram:test
```

## Scheduled Jobs

- `BUILD_UNIVERSE`
- `REFRESH_MARKET_DATA`
- `SCAN_SETUPS`
- `MONITOR_PAPER_POSITIONS`
- `CHECK_PROVIDERS`
- `SEND_DAILY_REPORT`

Each scheduled job writes execution state and uses a database lock.

## Safety

Live buying, live selling, wallet signing, private-key handling, futures, margin and leverage are not implemented.
