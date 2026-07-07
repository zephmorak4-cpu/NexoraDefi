from __future__ import annotations

from decimal import Decimal

from app.models import CandidateHistory, WalletPosition
from app.services.smart_money import aware
from app.trade_reconstruction.position_classifier import PositionClassifier
from app.trade_reconstruction.position_matcher import BUY_ACTIONS, SELL_ACTIONS
from app.trade_reconstruction.position_metrics import PositionMetrics


ZERO = Decimal("0")
HUNDRED = Decimal("100")


class PositionBuilder:
    def __init__(self) -> None:
        self.classifier = PositionClassifier()
        self.metrics = PositionMetrics()

    def build(self, wallet_id: int, token: str, rows: list[CandidateHistory]) -> WalletPosition | None:
        buys = [row for row in rows if row.action.lower() in BUY_ACTIONS]
        sells = [row for row in rows if row.action.lower() in SELL_ACTIONS]
        if not buys:
            return None
        quantity_bought = sum((Decimal(row.amount or 0) for row in buys), ZERO)
        quantity_sold = sum((Decimal(row.amount or 0) for row in sells), ZERO)
        buy_value = sum((Decimal(row.usd_value or 0) for row in buys), ZERO)
        sell_value = sum((Decimal(row.usd_value or 0) for row in sells), ZERO)
        if buy_value <= 0:
            return None
        if sells and sell_value <= 0:
            return None
        average_entry = buy_value / quantity_bought if quantity_bought > 0 and buy_value > 0 else ZERO
        average_exit = sell_value / quantity_sold if quantity_sold > 0 and sell_value > 0 else ZERO
        remaining = max(ZERO, quantity_bought - quantity_sold)
        sold_cost = average_entry * min(quantity_sold, quantity_bought)
        realized_pnl = sell_value - sold_cost if quantity_sold > 0 and average_entry > 0 else ZERO
        realized_roi = realized_pnl / sold_cost * HUNDRED if sold_cost > 0 else ZERO
        entry_time = aware(buys[0].timestamp)
        final_exit_time = aware(sells[-1].timestamp) if sells and remaining == 0 else None
        latest_activity = aware(rows[-1].timestamp)
        holding_end = final_exit_time or latest_activity
        holding_days = Decimal(str((holding_end - entry_time).total_seconds() / 86400))
        status = self._status(quantity_bought, quantity_sold, remaining, rows)
        position = WalletPosition(
            candidate_wallet_id=wallet_id,
            wallet_id=None,
            token_id=None,
            token_address=token,
            token_symbol=token[:8],
            entry_time=entry_time,
            final_exit_time=final_exit_time,
            first_buy_signature=buys[0].signature,
            last_sell_signature=sells[-1].signature if sells else None,
            total_bought_amount=quantity_bought,
            total_sold_amount=quantity_sold,
            current_balance=remaining,
            average_entry_price=average_entry,
            average_exit_price=average_exit,
            quantity_bought=quantity_bought,
            quantity_sold=quantity_sold,
            remaining_quantity=remaining,
            position_status=status,
            holding_period=holding_days,
            realized_profit=realized_pnl,
            unrealized_profit=ZERO,
            realized_pnl=realized_pnl,
            unrealized_pnl=ZERO,
            realized_roi=realized_roi,
            maximum_position_size=max((Decimal(row.usd_value or 0) for row in rows), default=ZERO),
            maximum_drawdown=abs(min(realized_roi, ZERO)),
            maximum_gain=max(realized_roi, ZERO),
            number_of_buys=len(buys),
            number_of_sells=len(sells),
            accumulation_events=max(len(buys) - 1, 0),
            distribution_events=len(sells),
            largest_buy=max((Decimal(row.usd_value or 0) for row in buys), default=ZERO),
            largest_sell=max((Decimal(row.usd_value or 0) for row in sells), default=ZERO),
            first_purchase_date=entry_time,
            latest_activity_date=latest_activity,
        )
        position.position_classification = self.classifier.classify(position)
        position.position_quality_score = self.metrics.quality_score(position)
        position.ai_analysis = self._analysis(position)
        return position

    @staticmethod
    def _status(quantity_bought: Decimal, quantity_sold: Decimal, remaining: Decimal, rows: list[CandidateHistory]) -> str:
        if quantity_sold <= 0:
            age_days = Decimal(str((aware(rows[-1].timestamp) - aware(rows[0].timestamp)).total_seconds() / 86400))
            return "ABANDONED" if age_days > 90 else "OPEN"
        if remaining <= 0 or quantity_sold >= quantity_bought:
            return "CLOSED"
        return "PARTIALLY_CLOSED"

    @staticmethod
    def _analysis(position: WalletPosition) -> str:
        if position.position_status != "CLOSED":
            return "Position is still open or partially closed, so final performance remains incomplete."
        outcome = "successful" if Decimal(position.realized_roi or 0) > 0 else "failed"
        return (
            f"{position.token_address} was a {outcome} completed position with "
            f"{Decimal(position.realized_roi or 0):.2f}% realized ROI over "
            f"{Decimal(position.holding_period or 0):.2f} days."
        )
