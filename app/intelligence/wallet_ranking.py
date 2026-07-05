from __future__ import annotations

from app.intelligence.wallet_report import WalletIntelligenceReport


class WalletRankingEngine:
    def rank(self, reports: list[WalletIntelligenceReport]) -> list[WalletIntelligenceReport]:
        return sorted(
            reports,
            key=lambda item: (
                item.copy_performance_score,
                item.wallet_reputation_score,
                item.historical_accuracy,
                item.risk_score,
            ),
            reverse=True,
        )

