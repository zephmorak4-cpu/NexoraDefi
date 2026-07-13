# Incident Response

## Database Outage

Symptoms:

- `/health/ready` returns `503`.
- Database status is `offline`.
- Scheduler jobs fail or are skipped.

Actions:

1. Verify Supabase/PostgreSQL project is active.
2. Verify `DATABASE_URL` on Render.
3. Check Render logs for connection or migration errors.
4. Do not switch to SQLite in production.

## Provider Rate Limit

Symptoms:

- Provider health degraded or rate-limited.
- Market refresh stores fewer candles.
- Scan funnel reports missing or insufficient data.

Actions:

1. Wait for rate-limit window.
2. Verify Birdeye/GeckoTerminal quotas.
3. Avoid lowering strategy standards to force signals.

## Telegram Failure

Actions:

1. Run `telegram:test`.
2. Confirm bot was started by the target chat.
3. Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` on Render.

## Deployment Incident

Actions:

1. Check `/health/live`.
2. Check `/health/ready`.
3. Review Render logs.
4. Roll back to previous deploy if startup or migrations fail.
