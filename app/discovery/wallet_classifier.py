from __future__ import annotations

from collections import Counter

from app.models import CandidateHistory


class WalletClassifier:
    def classify(self, history: list[CandidateHistory]) -> str:
        if not history:
            return "Unknown"
        actions = Counter(item.action.lower() for item in history)
        total = len(history)
        if actions["liquidity_add"] / total >= 0.35:
            return "Liquidity Provider"
        if actions["stake"] / total >= 0.35:
            return "Long-Term Investor"
        if total >= 20:
            return "High Frequency Trader"
        if any((item.usd_value or 0) >= 100_000 for item in history):
            return "Whale"
        if actions["swap"] / total >= 0.50:
            return "Market Maker"
        return "Unknown"

