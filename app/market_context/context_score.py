from __future__ import annotations

from decimal import Decimal

from app.core.config import Settings
from app.services.smart_money import clamp


class MarketContextScorer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def score(self, factors: dict[str, Decimal | None]) -> Decimal | None:
        available = {key: value for key, value in factors.items() if value is not None}
        if len(available) < 3:
            return None
        weights = self.settings.position_market_context_weights
        total_weight = sum(Decimal(str(weights[key])) for key in available)
        if total_weight <= 0:
            return None
        weighted = sum(Decimal(value) * Decimal(str(weights[key])) for key, value in available.items())
        return clamp(weighted / total_weight)
