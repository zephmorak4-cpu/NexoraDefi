from __future__ import annotations

from collections import Counter
from decimal import Decimal

from app.intelligence.wallet_report import WalletIntelligenceReport
from app.intelligence.wallet_ranking import WalletRankingEngine


class WalletPortfolioSummary:
    def build(self, reports: list[WalletIntelligenceReport]) -> dict[str, object]:
        ranked = WalletRankingEngine().rank(reports)
        return {
            "total_wallets": len(reports),
            "average_copy_performance": self._avg([item.copy_performance_score for item in reports]),
            "average_reputation": self._avg([item.wallet_reputation_score for item in reports]),
            "average_historical_accuracy": self._avg([item.historical_accuracy for item in reports]),
            "average_holding_period": self._avg([item.average_holding_time_days for item in reports]),
            "average_roi": self._avg([item.average_roi for item in reports]),
            "average_win_rate": self._avg([item.historical_accuracy for item in reports]),
            "average_drawdown": self._avg([item.maximum_drawdown for item in reports]),
            "trading_style_distribution": dict(Counter(item.trading_style for item in reports)),
            "risk_distribution": dict(Counter(item.risk_classification for item in reports)),
            "top_10_wallets": [item.wallet_address for item in ranked[:10]],
            "bottom_10_wallets": [item.wallet_address for item in ranked[-10:]],
            "most_consistent_wallet": self._best(ranked, "consistency"),
            "highest_returning_wallet": self._best(ranked, "average_roi"),
            "safest_wallet": self._best(ranked, "risk_score"),
            "most_aggressive_wallet": self._best(ranked, "total_trades"),
        }

    @staticmethod
    def _avg(values: list[Decimal]) -> Decimal:
        return sum(values, Decimal("0")) / Decimal(len(values)) if values else Decimal("0")

    @staticmethod
    def _best(reports: list[WalletIntelligenceReport], field: str) -> str | None:
        if not reports:
            return None
        return max(reports, key=lambda item: getattr(item, field)).wallet_address

