# Nexora DeFi MVP

Telegram-first Smart Money Intelligence Platform.

Nexora identifies promising crypto tokens by tracking high-quality wallets before broader market attention arrives. The MVP keeps the production foundation, Smart Money intelligence, basic token growth/momentum metrics, basic risk filters, and AI analyst reports for Telegram-ready summaries.

## Architecture

```text
External APIs -> collectors -> normalized records -> SQLAlchemy repository -> database
                         ^                              ^
                  APScheduler jobs               Alembic migrations
                         |
                 FastAPI lifecycle

transactions -> wallet positions -> wallet metrics -> wallet scores
                                             |
qualified wallet activity -> Smart Money detector -> smart_money_signals
                                             |
known token contracts -> transfer streams -> wallet discovery -> auto-tracked wallets
                                             |
price + liquidity history -> growth/momentum metrics
                                             |
holder/liquidity/volatility/smart exits -> basic risk filter
                                             |
structured Smart Money evidence -> AI analyst -> Telegram-ready reports
```

## Kept Modules

- Foundation: FastAPI, async database sessions, Alembic, logging, configuration, scheduler, collectors, repository, health checks, and tests.
- Smart Money Intelligence: wallet tracking, wallet profiling, scoring, elite wallet detection, whale/cluster style signal detection, and Smart Money signal APIs.
- Token Support Metrics: token growth, liquidity, and basic momentum metrics used to support Smart Money interpretation.
- Basic Risk Filter: liquidity, holder concentration, Smart Money exit, volatility, age, and lightweight contract availability checks.
- AI Analyst: evidence-only Smart Money reports with Telegram formatting.

Removed from the active MVP: historical pattern intelligence, market context intelligence, decision intelligence, portfolio intelligence, sector rotation, capital flow, backtesting, validation, weight optimization, confidence calibration, continuous learning, prediction outcomes, performance analytics, drift detection, and portfolio recommendations.

## Setup

Python 3.12 or newer is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

For local development, missing API credentials cause affected collectors to log a skip. Set `APP_ENV=production` to enforce required production secrets at startup.

## Production Credentials

The MVP preserves the existing configured integrations and environment names:

- `DATABASE_URL`
- `ETHERSCAN_API_KEY`
- `MORALIS_API_KEY`
- `COINGECKO_API_KEY`
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `CRYPTOPANIC_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `OPENAI_API_KEY` when `ANALYST_PROVIDER=openai`

Do not commit real secrets. Keep them in `.env`, platform environment settings, or your secret manager.

## Database

Active MVP tables:

- Foundation: `tokens`, `wallets`, `transactions`, `price_history`, `social_signals`, `market_signals`, `news_articles`, `alerts`, `users`
- Smart Money: `wallet_metrics`, `wallet_scores`, `wallet_positions`, `smart_money_signals`
- Token support: `token_growth_metrics`, `momentum_metrics`
- Risk: `token_risk_metrics`, `risk_events`

The migration `9f0b7c1d2e34_refactor_to_smart_money_mvp.py` removes non-MVP tables while preserving the migration chain.

## API

- `GET /health`
- `GET /ready`
- `GET /smart-money/wallets`
- `GET /smart-money/wallets/{address}`
- `GET /smart-money/signals`
- `GET /smart-money/top-wallets`
- `GET /smart-money/tokens/{token_id}`
- `GET /tokens/watchlist`
- `GET /tokens/trending`
- `GET /tokens/{token_id}/growth`
- `GET /tokens/{token_id}/momentum`
- `GET /risk/tokens/{token_id}`
- `GET /risk/events`
- `GET /risk/high-risk`
- `GET /risk/low-risk`
- `GET /analyst/token/{token_id}`
- `GET /analyst/watchlist`
- `GET /analyst/smart-money`

## Scheduled Jobs

The scheduler now runs only MVP jobs:

- Blockchain, market, social, and news refreshes. Moralis is used for wallet token transfers when `MORALIS_API_KEY` is present; otherwise the collector falls back to Etherscan.
- Wallet analysis
- Wallet scoring
- Automatic wallet discovery from known token contract transfer streams
- Smart Money signal generation
- Token rapid change, growth, and momentum metrics
- Risk volatility, risk score, and risk event checks
- Analyst report generation
- Telegram Smart Money alerts and daily summary delivery

## Telegram

The MVP uses Telegram's HTTP Bot API directly. Configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in local or deployment environment settings. The bot sends:

- Smart Money alerts
- Watchlist-ready analyst reports
- Daily Smart Money summaries

The supported command vocabulary for the bot UX is `/start`, `/help`, `/signals`, `/watchlist`, `/settings`, and `/latest`; command handling can be attached through a webhook or polling process without changing the intelligence core.

## AI Reports

Every Smart Money alert report uses structured evidence only and includes:

- Token
- Wallet Activity
- Why It Matters
- Risk Summary
- Confidence Score
- Suggested Action

The analyst prompt explicitly forbids inventing facts, prices, wallets, risks, or recommendations.

To use OpenAI for analyst wording, set:

```powershell
ANALYST_PROVIDER=openai
ANALYST_MODEL=your-preferred-openai-model
OPENAI_API_KEY=your_openai_api_key
```

Without those values, the platform uses deterministic templates.

## Validation

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m alembic upgrade head
```

The local MVP validation currently passes with 50 tests.

## Render

Render can deploy directly from the committed `render.yaml` blueprint:

- Runtime: Python
- Branch: `development`
- Build command: `pip install -e .`
- Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`

Use Render Blueprint deployment from `zephmorak4-cpu/NexoraDefi` and set all `sync: false` secrets in the Render dashboard. Keep real API keys out of Git.

## Railway

Railway uses the committed `railway.json`:

- Builder: Nixpacks
- Build command: `pip install -e .`
- Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Set production secrets in Railway Variables, never in Git. Required production values include `APP_ENV=production`, `DATABASE_URL`, blockchain/market/social/news keys, Telegram credentials, and OpenAI analyst credentials when `ANALYST_PROVIDER=openai`.
