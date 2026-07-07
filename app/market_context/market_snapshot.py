from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class MarketSnapshot:
    timestamp: datetime | None
    market_cap: Decimal | None = None
    liquidity: Decimal | None = None
    holder_count: int | None = None
    daily_volume: Decimal | None = None
    price: Decimal | None = None
    token_age_days: Decimal | None = None


def growth(entry: Decimal | int | None, exit: Decimal | int | None) -> Decimal | None:
    if entry is None or exit is None:
        return None
    entry_decimal = Decimal(entry)
    exit_decimal = Decimal(exit)
    if entry_decimal <= 0:
        return None
    return (exit_decimal - entry_decimal) / entry_decimal * Decimal("100")
