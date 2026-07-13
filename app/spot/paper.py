from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import PaperFill, PaperPosition
from app.spot.repositories import SpotRepository, dec
from app.spot.types import Candle, PaperTradeState, TradePlan


@dataclass(frozen=True)
class PaperFillResult:
    filled: bool
    state: PaperTradeState
    reason: str


class PaperBroker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create_waiting_position(self, session: AsyncSession, plan: TradePlan) -> PaperPosition | None:
        repo = SpotRepository(session)
        await repo.default_account(self.settings.paper_account_starting_balance_usd)
        if await repo.open_positions_count() >= self.settings.max_open_paper_trades:
            return None
        row = PaperPosition(
            signal_fingerprint=plan.fingerprint,
            token_address=plan.token.address,
            state=PaperTradeState.WAITING_FOR_ENTRY.value,
            stop_loss=dec(plan.stop_loss) or Decimal("0"),
            target_1=dec(plan.targets[0]) or Decimal("0"),
            target_2=dec(plan.targets[1]) or Decimal("0"),
            target_3=dec(plan.targets[2]) or Decimal("0"),
        )
        session.add(row)
        return row

    def try_entry(self, position: PaperPosition, plan: TradePlan, candle: Candle) -> PaperFillResult:
        if position.state != PaperTradeState.WAITING_FOR_ENTRY.value:
            return PaperFillResult(False, PaperTradeState(position.state), "position not waiting")
        if candle.high < plan.entry_low or candle.low > plan.entry_high:
            return PaperFillResult(False, PaperTradeState.WAITING_FOR_ENTRY, "entry zone not touched")
        entry = min(max(candle.close, plan.entry_low), plan.entry_high)
        entry *= 1 + self.settings.estimated_slippage_bps / 10000
        stop_distance = entry - plan.stop_loss
        if stop_distance <= 0:
            return PaperFillResult(False, PaperTradeState.CANCELLED, "invalid stop distance")
        risk_usd = self.settings.paper_account_starting_balance_usd * self.settings.risk_per_paper_trade_percent / 100
        quantity = risk_usd / stop_distance
        position.entry_price = dec(entry)
        position.quantity = dec(quantity)
        position.state = PaperTradeState.OPEN.value
        position.opened_at = datetime.now(timezone.utc)
        return PaperFillResult(True, PaperTradeState.OPEN, "entry filled")

    def update_open_position(self, position: PaperPosition, candle: Candle) -> PaperFillResult:
        if position.state != PaperTradeState.OPEN.value or position.entry_price is None or position.quantity is None:
            return PaperFillResult(False, PaperTradeState(position.state), "position not open")
        stop = float(position.stop_loss)
        tp2 = float(position.target_2)
        entry = float(position.entry_price)
        quantity = float(position.quantity)
        if candle.low <= stop and candle.high >= tp2 and self.settings.conservative_intrabar_fills:
            exit_price = stop
            state = PaperTradeState.CLOSED_SL
            reason = "stop and target touched; conservative stop-first fill"
        elif candle.low <= stop:
            exit_price = stop
            state = PaperTradeState.CLOSED_SL
            reason = "stop loss reached"
        elif candle.high >= tp2:
            exit_price = tp2
            state = PaperTradeState.CLOSED_TP
            reason = "primary target reached"
        else:
            return PaperFillResult(False, PaperTradeState.OPEN, "no exit")
        gross = (exit_price - entry) * quantity
        fees = abs(exit_price * quantity) * self.settings.estimated_fees_bps / 10000
        position.realized_pnl_usd = dec(gross - fees) or Decimal("0")
        position.state = state.value
        position.closed_at = datetime.now(timezone.utc)
        return PaperFillResult(True, state, reason)

    @staticmethod
    def fill(position: PaperPosition, fill_type: str, price: float, quantity: float, fee_usd: float = 0) -> PaperFill:
        return PaperFill(position_id=position.id, fill_type=fill_type, price=dec(price) or Decimal("0"), quantity=dec(quantity) or Decimal("0"), fee_usd=dec(fee_usd) or Decimal("0"))

