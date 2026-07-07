from __future__ import annotations

from decimal import Decimal

from app.services.smart_money import clamp


class LiquidityAnalyzer:
    def score(self, liquidity: Decimal | None, liquidity_growth: Decimal | None) -> Decimal | None:
        if liquidity is None:
            return None
        size_score = clamp(liquidity / Decimal("100000") * Decimal("100"))
        growth_score = clamp(Decimal("50") + (liquidity_growth or Decimal("0")))
        return clamp(size_score * Decimal("0.60") + growth_score * Decimal("0.40"))
