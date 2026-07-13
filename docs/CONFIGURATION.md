# Configuration

Configuration is in `app/core/config.py` and `.env.example`.

## Safety Defaults

```text
DRY_RUN=true
PAPER_TRADING_ENABLED=true
LIVE_TRADING_ENABLED=false
SUPPORTED_CHAIN=solana
```

Startup validation rejects live trading, non-Solana mode, invalid universe sizes, invalid thresholds, and invalid paper-risk values.

## Critical Variables

- `DATABASE_URL`
- `DEXSCREENER_ENABLED`
- `GECKOTERMINAL_ENABLED`
- `PAPER_TRADING_ENABLED`
- `LIVE_TRADING_ENABLED`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Telegram variables are critical only when `TELEGRAM_SIGNALS_ENABLED=true`.

## Strategy Variables

- `SIGNAL_EMA_FAST`
- `SIGNAL_EMA_SLOW`
- `SIGNAL_ATR_PERIOD`
- `SIGNAL_VOLUME_MULTIPLIER`
- `SIGNAL_MIN_REWARD_RISK`
- `SIGNAL_MIN_QUALITY_SCORE`
- `MAX_STOP_DISTANCE_PERCENT`
- `MIN_STOP_DISTANCE_PERCENT`

## Universe Variables

- `TARGET_UNIVERSE_SIZE`
- `CANDIDATE_UNIVERSE_SIZE`
- `MIN_TOKEN_AGE_DAYS`
- `MIN_LIQUIDITY_USD`
- `MIN_VOLUME_24H_USD`
- `MIN_MARKET_CAP_USD`
- `MIN_HISTORY_DAYS`
- `MIN_DATA_COMPLETENESS`

Do not commit real secrets. Put production values in Render or Railway environment variables.
