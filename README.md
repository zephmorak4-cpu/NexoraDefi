# Nexora DeFi MVP

Telegram-first Solana Smart Money Intelligence Platform.

Nexora identifies promising Solana opportunities by monitoring curated elite wallets before broader market attention arrives. The MVP keeps the production foundation, Smart Money intelligence, basic token growth/momentum metrics, basic risk filters, and AI analyst reports for Telegram-ready summaries.

## Architecture

```text
External APIs -> collectors -> normalized records -> SQLAlchemy repository -> database
                         ^                              ^
                  APScheduler jobs               Alembic migrations
                         |
                 FastAPI lifecycle

curated Solana wallets -> wallet activity -> wallet reputation
                                             |
Solana activity scanner -> candidate wallets -> observation -> promotion
                                             |
qualified wallet activity -> Smart Money detector -> smart_money_signals
                                             |
Solana wallet monitor -> token quality -> conviction score -> Telegram alerts
                                             |
price + liquidity history -> growth/momentum metrics
                                             |
holder/liquidity/volatility/smart exits -> basic risk filter
                                             |
structured Smart Money evidence -> AI analyst -> Telegram-ready reports
```

## Kept Modules

- Foundation: FastAPI, async database sessions, Alembic, logging, configuration, scheduler, collectors, repository, health checks, and tests.
- Smart Money Intelligence: curated Solana wallet tracking, wallet activity monitoring, wallet reputation scoring, token quality scoring, conviction scoring, and Smart Money signal APIs.
- Smart Wallet Discovery: Solana candidate wallet discovery, observation, scoring, classification, promotion, and demotion. Candidate wallets never generate Telegram alerts.
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

Required for production Smart Money MVP startup:

- `DATABASE_URL`
- `MORALIS_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional integrations that enrich collection or report wording:

- `COINGECKO_API_KEY`
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `CRYPTOPANIC_API_KEY`
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
- `POST /admin/wallets/add`
- `POST /admin/wallets/remove`
- `GET /admin/wallets`
- `GET /admin/wallet-reputation`
- `GET /admin/token-quality`
- `GET /admin/conviction`
- `GET /admin/wallet-activity`
- `GET /admin/signals`
- `GET /admin/candidates`
- `GET /admin/candidate/{id}`
- `POST /admin/promote`
- `POST /admin/reject`
- `GET /admin/elite-wallets`
- `GET /admin/discovery-stats`

## Scheduled Jobs

The scheduler now runs only MVP jobs:

- Solana wallet monitoring, market, social, and news refreshes. Moralis is used for Solana wallet activity when `MORALIS_API_KEY` is present.
- Wallet analysis
- Wallet scoring
- Candidate wallet discovery every 5 minutes
- Candidate scoring and reputation refresh hourly
- Candidate promotion review daily
- Elite wallet demotion review weekly
- Curated Solana wallet monitoring
- Solana wallet reputation scoring
- Solana token quality scoring
- Solana conviction-gated alert generation
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

## Smart Wallet Discovery

The discovery engine scans Solana activity and places promising wallets into a candidate pool. Candidate wallets are observation-only: they are scored and classified, but they do not trigger Telegram alerts.

Candidate scoring uses configurable weights:

- Transaction Size: 25%
- Consistency: 20%
- Early Entry: 20%
- Token Quality: 15%
- Holding Behaviour: 10%
- Network Influence: 10%

Wallet classifications are informational and include Whale, High Frequency Trader, Long-Term Investor, Market Maker, Liquidity Provider, and Unknown.

Promotion requires the observation period to complete, wallet reputation at or above 85, candidate score at or above 85, historical accuracy above the configured threshold, and low suspicious behaviour. If an elite wallet deteriorates, the demotion job moves it back into observation.

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

Use Render Blueprint deployment from `zephmorak4-cpu/NexoraDefi` and set all `sync: false` secrets in the Render dashboard. Keep real API keys out of Git. The Render development blueprint uses deterministic analyst templates by default so reports stay fully evidence-bound.

## Railway

Railway uses the committed `railway.json`:

- Builder: Nixpacks
- Build command: `pip install -e .`
- Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Set production secrets in Railway Variables, never in Git. Required production values include `APP_ENV=production`, `DATABASE_URL`, `MORALIS_API_KEY`, and Telegram credentials. Market, social, news, and OpenAI analyst credentials are optional enrichments.
