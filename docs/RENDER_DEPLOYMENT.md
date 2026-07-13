# Render Deployment

## Current Deployment Audit

Application language: Python 3.12  
Framework: FastAPI  
Package manager: pip / editable Python package  
Current Render service type: web  
Current Render plan: `starter` in `render.yaml`  
Deployment branch: `development`  
Build command: `pip install -e .`  
Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`  
Health-check path: `/health/live`  
Scheduler: APScheduler inside the web process, guarded by database job locks  

## Runtime Decision

Selected: paid always-on Render web service.

Reason:

- Five-minute paper-position monitoring is required.
- Fifteen-minute setup scans should run predictably after candle windows.
- The scheduler already runs inside the application.
- Free web services can sleep and miss scan windows.

Required user action:

- Keep the Render service on an always-on paid plan.
- Do not rely on self-ping loops as production scheduling.

## Environment Variables

Required:

- `DATABASE_URL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `PAPER_TRADING_ENABLED=true`
- `LIVE_TRADING_ENABLED=false`
- `DEXSCREENER_ENABLED=true`
- `GECKOTERMINAL_ENABLED=true`
- `BIRDEYE_ENABLED=true`
- `BIRDEYE_API_KEY`

Recommended:

- `COINGECKO_ENABLED=false` until the key is verified.
- `DRY_RUN=true`

## Deploy

1. Push `development`.
2. Confirm Render environment variables.
3. Trigger deploy or wait for auto-deploy.
4. Verify `/health/live`.
5. Verify `/health/ready`.
6. Run manual diagnostics from a shell using the same environment.

## Rollback

Use Render rollback to the last known-good deploy. Because paper state is stored in the database, rollback must not use local SQLite state.
