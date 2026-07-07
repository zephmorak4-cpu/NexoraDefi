from __future__ import annotations

from decimal import Decimal

from app.services.smart_money import clamp


class VolumeAnalyzer:
    def score(self, daily_volume: Decimal | None, volume_growth: Decimal | None) -> Decimal | None:
        if daily_volume is None:
            return None
        size_score = clamp(daily_volume / Decimal("250000") * Decimal("100"))
        growth_score = clamp(Decimal("50") + (volume_growth or Decimal("0")))
        return clamp(size_score * Decimal("0.45") + growth_score * Decimal("0.55"))
