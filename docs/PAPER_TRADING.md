# Paper Trading

Paper trading is simulated only.

## Lifecycle

```text
QUALIFIED signal
  -> WAITING_FOR_ENTRY position
  -> OPEN if price trades inside entry zone
  -> CLOSED_TP or CLOSED_SL using conservative fill rules
```

## Risk

Position size is based on fixed account risk:

```text
risk_usd = paper_account_balance * RISK_PER_PAPER_TRADE_PERCENT
quantity = risk_usd / (entry - stop)
```

Quality score never increases risk.

## Conservative Intrabar Rule

If a candle touches stop and target and ordering is unknown, the stop is assumed first when `CONSERVATIVE_INTRABAR_FILLS=true`.

## Inspect

```powershell
.venv\Scripts\python.exe -m app.spot.cli paper:positions
.venv\Scripts\python.exe -m app.spot.cli paper:trades
```
