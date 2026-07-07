from __future__ import annotations

from collections import Counter
from decimal import Decimal

from app.models import WalletPosition


ZERO = Decimal("0")


class PositionSummary:
    def build(self, positions: list[WalletPosition]) -> dict[str, object]:
        closed = [item for item in positions if item.position_status == "CLOSED"]
        winners = [item for item in closed if Decimal(item.realized_roi or 0) > 0]
        losers = [item for item in closed if Decimal(item.realized_roi or 0) < 0]
        open_positions = [item for item in positions if item.position_status in {"OPEN", "PARTIALLY_CLOSED"}]
        return {
            "total_positions": len(positions),
            "winning_positions": len(winners),
            "losing_positions": len(losers),
            "open_positions": len(open_positions),
            "closed_positions": len(closed),
            "largest_winner": self._token(max(winners, key=lambda item: Decimal(item.realized_roi or 0), default=None)),
            "largest_loser": self._token(min(losers, key=lambda item: Decimal(item.realized_roi or 0), default=None)),
            "average_roi": self._avg([Decimal(item.realized_roi or 0) for item in closed]),
            "average_holding_time": self._avg([Decimal(item.holding_period or 0) for item in positions]),
            "average_position_size": self._avg([Decimal(item.maximum_position_size or 0) for item in positions]),
            "portfolio_diversification": len({item.token_address for item in positions if item.token_address}),
            "best_performing_token": self._token(max(winners, key=lambda item: Decimal(item.realized_roi or 0), default=None)),
            "worst_performing_token": self._token(min(losers, key=lambda item: Decimal(item.realized_roi or 0), default=None)),
            "position_quality_distribution": dict(Counter(item.position_classification for item in positions)),
        }

    @staticmethod
    def _avg(values: list[Decimal]) -> Decimal:
        return sum(values, ZERO) / Decimal(len(values)) if values else ZERO

    @staticmethod
    def _token(position: WalletPosition | None) -> str | None:
        return position.token_address if position else None
