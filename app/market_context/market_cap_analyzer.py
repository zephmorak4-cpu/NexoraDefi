from __future__ import annotations

from decimal import Decimal

from app.services.smart_money import clamp


class MarketCapAnalyzer:
    def score(self, market_cap: Decimal | None, market_cap_growth: Decimal | None) -> Decimal | None:
        if market_cap is None:
            return None
        early_score = clamp(Decimal("100") - market_cap / Decimal("1000000") * Decimal("100"))
        growth_score = clamp(Decimal("50") + (market_cap_growth or Decimal("0")))
        return clamp(early_score * Decimal("0.55") + growth_score * Decimal("0.45"))
