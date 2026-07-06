from __future__ import annotations

from collections import Counter
from decimal import Decimal

from app.models import CandidateHistory


class WalletPipelineValidator:
    min_transactions = 5
    min_token_events = 2

    def has_complete_transactions(self, history: list[CandidateHistory]) -> bool:
        if len(history) < self.min_transactions:
            return False
        return all(item.timestamp and item.token and item.action for item in history)

    def has_portfolio_evidence(self, history: list[CandidateHistory]) -> bool:
        values = [Decimal(item.usd_value) for item in history if item.usd_value is not None]
        return bool(values) and sum(values, Decimal("0")) > 0

    def has_token_history(self, history: list[CandidateHistory]) -> bool:
        token_counts = Counter(item.token for item in history if item.token)
        return any(count >= self.min_token_events for count in token_counts.values())

    def has_completed_backtest_data(self, history: list[CandidateHistory]) -> bool:
        actions = {item.action.lower() for item in history}
        has_entry = bool(actions.intersection({"buy", "swap", "accumulate", "liquidity_add"}))
        has_exit = bool(actions.intersection({"sell", "out", "liquidity_remove"}))
        return has_entry and has_exit and self.has_token_history(history)
