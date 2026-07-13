# Debugging

## Check Readiness

```powershell
.venv\Scripts\python.exe -m app.spot.cli system:status --live
.venv\Scripts\python.exe -m app.spot.cli providers:check
```

If state is `NOT_READY`, inspect `missing_capabilities`.

## No Signals

Run:

```powershell
.venv\Scripts\python.exe -m app.spot.cli universe:show --tier CORE
.venv\Scripts\python.exe -m app.spot.cli scan:funnel
.venv\Scripts\python.exe -m app.spot.cli signals:recent
```

Interpretation:

- CORE count is zero: universe filters blocked all candidates.
- Provider missing capability: scanner was correctly blocked.
- Rejection reasons dominate: scanner is working but no setup qualified.
- Signals exist but Telegram absent: notification config is missing.

## Validate One Token

```powershell
.venv\Scripts\python.exe -m app.spot.cli market:validate --token=<mint>
```

This reports selected pool, quote, latest candle timestamps, missing intervals, malformed counts, and sources.
