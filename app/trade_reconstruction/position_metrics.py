from __future__ import annotations

from decimal import Decimal
from statistics import median

from app.models import WalletPosition
from app.services.smart_money import clamp


ZERO = Decimal("0")
HUNDRED = Decimal("100")


class PositionMetrics:
    def quality_score(self, position: WalletPosition) -> Decimal:
        roi = Decimal(position.realized_roi or 0)
        holding_days = Decimal(position.holding_period or 0)
        drawdown = Decimal(position.maximum_drawdown or 0)
        risk_penalty = min(drawdown, HUNDRED) * Decimal("0.25")
        roi_component = clamp(roi + Decimal("50")) * Decimal("0.45")
        hold_component = clamp(min(holding_days, Decimal("90")) / Decimal("90") * HUNDRED) * Decimal("0.20")
        discipline = Decimal("20") if position.position_status in {"CLOSED", "PARTIALLY_CLOSED"} else Decimal("10")
        return clamp(roi_component + hold_component + discipline - risk_penalty)

    def profit_factor(self, positions: list[WalletPosition]) -> Decimal:
        gains = sum((Decimal(item.realized_pnl or 0) for item in positions if Decimal(item.realized_pnl or 0) > 0), ZERO)
        losses = abs(sum((Decimal(item.realized_pnl or 0) for item in positions if Decimal(item.realized_pnl or 0) < 0), ZERO))
        return gains / losses if losses > 0 else gains

    def sharpe_ratio(self, positions: list[WalletPosition]) -> Decimal:
        returns = [Decimal(item.realized_roi or 0) for item in positions if item.position_status == "CLOSED"]
        if len(returns) < 2:
            return ZERO
        avg = sum(returns, ZERO) / Decimal(len(returns))
        variance = sum((value - avg) ** 2 for value in returns) / Decimal(len(returns) - 1)
        stddev = Decimal(str(float(variance) ** 0.5))
        return avg / stddev if stddev else ZERO

    def median_roi(self, positions: list[WalletPosition]) -> Decimal:
        values = [Decimal(item.realized_roi or 0) for item in positions if item.position_status == "CLOSED"]
        return Decimal(str(median(values))) if values else ZERO
