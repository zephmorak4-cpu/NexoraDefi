# API Requirements Report

Generated from the local smoke test on 2026-07-13 and updated after Telegram/Birdeye configuration.

## Critical Missing APIs

None currently missing for local paper-observation checks.

## Critical Providers Working

- DexScreener: `HEALTHY`, used for established market search and current quote checks.
- GeckoTerminal: `HEALTHY`, used for OHLCV capability.
- Birdeye: `HEALTHY`, used for quote/OHLCV fallback when quota allows.
- Telegram: `HEALTHY`, used for paper-trade notifications.
- Database: `HEALTHY`, used for persistence.

## Optional Missing APIs

- Helius: optional metadata/enrichment.
- Solana RPC: optional on-chain enrichment.
- Jupiter: optional quote validation only.
- OpenAI: optional explanation wording only.
- Discord: optional signal mirroring.

## Configured But Failing

CoinGecko:

- Failure: supplied key did not authenticate against tested public/demo/pro ping surfaces.
- Classification: optional provider unavailable.
- Required action: verify the CoinGecko plan/key type and exact host/header from the CoinGecko dashboard.

Birdeye:

- Status: key is valid for price checks.
- Note: OHLCV calls may still return `429 Too Many Requests`; the scanner now falls back safely and records no fake candles.

## Universe Build Result

- Raw candidates retrieved: 249
- Eligible: 3
- CORE: 3
- CANDIDATE: 0
- EXCLUDED: 246

Top exclusions:

- insufficient liquidity: 158
- insufficient 24h volume: 152
- insufficient market cap: 144
- pump.fun launch asset excluded: 57
- insufficient age: 15
- unsupported quote asset: 12

## Latest Scan Funnel

- Tokens evaluated: 3
- Signals generated: 0
- Rejection reasons:
  - valid consolidation not detected: 2
  - bearish regime blocked longs: 1
