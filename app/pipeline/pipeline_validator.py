from __future__ import annotations

from collections import Counter
from decimal import Decimal

from app.models import CandidateHistory
from app.models import CandidatePortfolioSnapshot, CandidateTokenHistory


class WalletPipelineValidator:
    min_transactions = 5
    min_token_events = 2

    def has_complete_transactions(self, history: list[CandidateHistory]) -> bool:
        if len(history) < self.min_transactions:
            return False
        return all(item.timestamp and item.token and item.action for item in history)

    def has_portfolio_evidence(self, snapshot: CandidatePortfolioSnapshot | None) -> bool:
        if snapshot is None:
            return False
        if snapshot.zero_assets_confirmed:
            return True
        return snapshot.total_value_usd is not None and Decimal(snapshot.total_value_usd) > 0

    def has_token_history(
        self,
        history: list[CandidateHistory],
        token_history: list[CandidateTokenHistory] | None = None,
    ) -> bool:
        if token_history:
            return any(item.purchase_count + item.sale_count >= self.min_token_events for item in token_history)
        token_counts = Counter(item.token for item in history if item.token)
        return any(count >= self.min_token_events for count in token_counts.values())

    def has_completed_backtest_data(
        self,
        history: list[CandidateHistory],
        token_history: list[CandidateTokenHistory] | None = None,
    ) -> bool:
        if token_history and any(item.roi is not None and item.sale_count > 0 for item in token_history):
            return True
        actions = {item.action.lower() for item in history}
        has_entry = bool(actions.intersection({"buy", "swap", "accumulate", "liquidity_add"}))
        has_exit = bool(actions.intersection({"sell", "out", "liquidity_remove"}))
        return has_entry and has_exit and self.has_token_history(history)
