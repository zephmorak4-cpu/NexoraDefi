from __future__ import annotations

from decimal import Decimal

from app.services.smart_money import clamp


class TokenAgeAnalyzer:
    def score(self, token_age_days: Decimal | None) -> Decimal | None:
        if token_age_days is None:
            return None
        if token_age_days < 0:
            return None
        return clamp(Decimal("100") - token_age_days / Decimal("30") * Decimal("100"))
