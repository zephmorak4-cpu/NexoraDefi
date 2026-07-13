# Repository Reset Report

## Backup

- Backup branch created: `backup/alpha-discovery-before-reset`

## Deleted Product Surface

- Removed `app/alpha_discovery/` product package.
- Removed `app/models/alpha.py` ORM models from active application imports.
- Removed old alpha API registration from `app/main.py`.
- Removed old alpha scheduler jobs from `app/jobs/scheduler.py`.
- Removed `tests/test_alpha_discovery.py`.

## Preserved Integrations

- Telegram transport remains in `app/telegram/client.py`.
- HTTP retry wrapper remains in `app/services/http.py`.
- Database connection remains in `app/database/session.py`.
- Logging remains in `app/core/logging.py`.
- Environment loading remains in `app/core/config.py`.
- Generic market-data clients are available in `app/integrations/market_data_clients.py`.
- Integration status helper is available in `app/integrations/health.py`.

## Runtime State

- No market scanner is registered.
- No signal engine is registered.
- No automatic Telegram alert is registered.
- No automatic Discord alert is registered.
- No automatic OpenAI analysis workflow is registered.
- No trade execution workflow is registered.

## Database Proposal

Obsolete product tables detected from historical migrations:

- `alpha_scanned_tokens`
- `alpha_alert_history`
- `alpha_watchlist_tokens`
- `alpha_smart_wallets`
- `alpha_provider_snapshots`

Action taken:

- Active application references removed.
- ORM models removed from the active model registry.
- Existing tables retained temporarily.
- No destructive database migration executed.
- Historical Alembic migrations retained to preserve migration chain integrity.

## Ready State

The repository now starts as a minimal reset runtime and is ready for future Spot Momentum Engine development. No Spot Momentum Engine logic has been implemented in this reset.
