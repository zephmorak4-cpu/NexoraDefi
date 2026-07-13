# API Requirements Report

Generated from the local smoke test on 2026-07-13.

## Critical Missing APIs

1. Capability: Telegram notifications
   Required for: delivering paper-trade alerts when `TELEGRAM_SIGNALS_ENABLED=true`
   Current provider status: `NOT_CONFIGURED`
   Recommended provider: Telegram Bot API
   Required environment variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   Official documentation: `https://core.telegram.org/bots/api`
   Free-tier suitability: suitable for MVP alert traffic
   Exact test after configuration:

```powershell
.venv\Scripts\python.exe -m app.spot.cli telegram:test
.venv\Scripts\python.exe -m app.spot.cli providers:check
```

## Critical Providers Working

- DexScreener: `HEALTHY`, used for discovery and current quote checks.
- GeckoTerminal: `HEALTHY`, used for OHLCV capability.
- Database: `HEALTHY`, used for persistence.

## Optional Missing APIs

- Helius: optional metadata/enrichment.
- Solana RPC: optional on-chain enrichment.
- Jupiter: optional quote validation only.
- OpenAI: optional explanation wording only.
- Discord: optional signal mirroring.

## Configured But Failing

None observed in the smoke test. Telegram is not failing authentication; it is not configured in the current process environment.

## Universe Build Result

- Candidates discovered: 37
- Eligible: 0
- CORE: 0
- CANDIDATE: 0
- EXCLUDED: 37

Top exclusions:

- insufficient market cap: 37
- insufficient liquidity: 36
- insufficient 24h volume: 18
- insufficient age: 17
- stablecoin excluded: 1
