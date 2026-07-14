# Render Deployment

## Current Deployment Audit

Application language: Python 3.12  
Framework: FastAPI  
Package manager: pip / editable Python package  
Current Render service type: web  
Current Render plan: `free`  
Deployment branch: `development`  
Build command: `pip install -e .`  
Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`  
Health-check path: `/health/live`  
Scheduler: APScheduler inside the web process, guarded by database job locks  

## Runtime Decision

Selected for current phase: free Render web service with external keep-awake pings.

Reason:

- Render free web services can sleep after idle periods.
- Internal self-ping loops are not reliable after the service has already slept because the app process is no longer running.
- A GitHub Actions workflow sends inbound traffic to `/health/live` every five minutes to reduce idle spin-down.
- This is acceptable for development/paper observation, but it is still not equivalent to an always-on paid service.

Required user action:

- Keep GitHub Actions enabled for the repository.
- Monitor Render free instance-hour usage.
- Upgrade to a paid instance before treating the scheduler as mission-critical production infrastructure.

Keep-awake workflow:

- `.github/workflows/keep-render-awake.yml`
- Schedule: every five minutes
- Target: `https://nexora-defi-dev.onrender.com/health/live`
- Manual trigger: GitHub Actions `workflow_dispatch`

Local backup ping loop:

- `scripts/keep_render_awake.ps1`
- Runs from this Windows machine while the machine is awake and connected.
- Use only as a backup; GitHub Actions is preferred because it does not depend on the local PC staying on.

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
- `TARGET_UNIVERSE_SIZE=30`
- `CANDIDATE_UNIVERSE_SIZE=100`
- `UNIVERSE_GECKO_PAGES=12`
- `UNIVERSE_DEX_SEARCH_QUERIES=solana,SOL,USDC,JUP,RAY,ORCA,BONK,WIF,JTO,PYTH,Jupiter,Raydium,Orca,Marinade,Kamino,Tensor,Drift,KMNO,DRIFT,JITOSOL,MSOL,INF,CLOUD,TNSR,GRASS,PENGU,PNUT,POPCAT,MEW,HNT,MOBILE,IO,ZEUS,W,RENDER`
- `MIN_TOKEN_AGE_DAYS=30`
- `MIN_LIQUIDITY_USD=100000`
- `MIN_VOLUME_24H_USD=250000`
- `MIN_MARKET_CAP_USD=0`
- `STRATEGY_EMA_FAST=12`
- `STRATEGY_EMA_SLOW=30`
- `SIGNAL_MIN_QUALITY_SCORE=70`

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
