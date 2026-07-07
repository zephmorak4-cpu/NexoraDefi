from __future__ import annotations

from decimal import Decimal

from app.models import WalletPosition


class PositionClassifier:
    def classify(self, position: WalletPosition) -> str:
        roi = Decimal(position.realized_roi or 0)
        holding_days = Decimal(position.holding_period or 0)
        remaining = Decimal(position.remaining_quantity or 0)
        sold = Decimal(position.quantity_sold or 0)
        bought = Decimal(position.quantity_bought or 0)
        if sold > 0 and remaining > 0:
            return "Partial Exit"
        if position.position_status == "CLOSED" and roi < 0:
            return "Failed Position"
        if position.number_of_buys >= 3 and remaining > 0 and holding_days >= 7:
            return "High Conviction Hold"
        if holding_days < Decimal("0.25"):
            return "Scalp"
        if holding_days <= 2:
            return "Quick Flip"
        if holding_days >= 30:
            return "Long Term Investment"
        if bought > 0 and sold > 0:
            return "Swing Trade"
        return "Unknown"
