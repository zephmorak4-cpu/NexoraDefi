from __future__ import annotations

from decimal import Decimal

from app.services.smart_money import clamp


class HolderAnalyzer:
    def score(self, holder_count: int | None, holder_growth: Decimal | None) -> Decimal | None:
        if holder_count is None:
            return None
        size_score = clamp(Decimal(holder_count) / Decimal("1000") * Decimal("100"))
        growth_score = clamp(Decimal("50") + (holder_growth or Decimal("0")))
        return clamp(size_score * Decimal("0.40") + growth_score * Decimal("0.60"))
