# APIs

## Provider Responsibilities

| Provider | Current Use | Required |
| --- | --- | --- |
| DexScreener | established market search, metadata, liquidity, volume, quote checks | yes |
| GeckoTerminal | OHLCV candle source | yes |
| Birdeye | quote and OHLCV fallback when configured | no |
| Telegram | paper-trade alerts and test messages | yes when Telegram alerts are enabled |
| Database | persistence and restart safety | yes |
| Helius | optional Solana metadata/enrichment | no |
| Solana RPC | optional on-chain enrichment | no |
| Jupiter | optional quote validation only | no |
| CoinGecko | optional market-data health check; never used for synthetic candles | no |
| OpenAI | optional wording after deterministic plan | no |

## Official Locations

- DexScreener API: `https://docs.dexscreener.com/api/reference`
- GeckoTerminal API: `https://www.geckoterminal.com/dex-api`
- Telegram Bot API: `https://core.telegram.org/bots/api`
- Jupiter API: `https://dev.jup.ag/docs`
- Helius API: `https://docs.helius.dev/`
- Birdeye API: `https://docs.birdeye.so/`
- CoinGecko API: `https://docs.coingecko.com/`

## Failure Behavior

Missing critical capabilities place readiness in `NOT_READY`. The scanner will not generate signals or create paper trades when a required capability is missing.

Use:

```powershell
.venv\Scripts\python.exe -m app.spot.cli providers:check
```

## Current Live Smoke Result

On 2026-07-13, the latest live provider audit returned:

- DexScreener: `HEALTHY`
- GeckoTerminal: `HEALTHY`
- Birdeye: `HEALTHY`
- Telegram: `HEALTHY`
- Database: `HEALTHY`
- CoinGecko: optional provider check failed with the supplied key

Readiness has no missing critical capabilities. CoinGecko is optional and is not required for paper-observation readiness.
