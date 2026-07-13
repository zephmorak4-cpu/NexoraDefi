# APIs

## Provider Responsibilities

| Provider | Current Use | Required |
| --- | --- | --- |
| DexScreener | token/pool discovery, metadata, liquidity, volume, quote checks | yes |
| GeckoTerminal | OHLCV candle source | yes |
| Telegram | paper-trade alerts and test messages | yes when Telegram alerts are enabled |
| Database | persistence and restart safety | yes |
| Helius | optional Solana metadata/enrichment | no |
| Solana RPC | optional on-chain enrichment | no |
| Jupiter | optional quote validation only | no |
| OpenAI | optional wording after deterministic plan | no |

## Official Locations

- DexScreener API: `https://docs.dexscreener.com/api/reference`
- GeckoTerminal API: `https://www.geckoterminal.com/dex-api`
- Telegram Bot API: `https://core.telegram.org/bots/api`
- Jupiter API: `https://dev.jup.ag/docs`
- Helius API: `https://docs.helius.dev/`

## Failure Behavior

Missing critical capabilities place readiness in `NOT_READY`. The scanner will not generate signals or create paper trades when a required capability is missing.

Use:

```powershell
.venv\Scripts\python.exe -m app.spot.cli providers:check
```

## Current Live Smoke Result

On 2026-07-13, live provider audit returned:

- DexScreener: `HEALTHY`
- GeckoTerminal: `HEALTHY`
- Database: `HEALTHY`
- Telegram: `NOT_CONFIGURED`

Readiness remains `NOT_READY` because Telegram alerts are enabled but Telegram credentials are not visible to the running environment.
