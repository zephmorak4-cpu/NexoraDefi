from __future__ import annotations

from collections import defaultdict

from app.models import CandidateHistory


BUY_ACTIONS = {"buy", "swap", "accumulate", "liquidity_add"}
SELL_ACTIONS = {"sell", "out", "liquidity_remove"}
IGNORED_ACTIONS = {"airdrop", "dust", "failed", "failed_swap", "migration"}


class PositionMatcher:
    def group(self, history: list[CandidateHistory]) -> dict[tuple[int, str], list[CandidateHistory]]:
        grouped: dict[tuple[int, str], list[CandidateHistory]] = defaultdict(list)
        for item in history:
            action = item.action.lower()
            if action in IGNORED_ACTIONS or not item.token:
                continue
            if item.amount is not None and item.amount <= 0:
                continue
            grouped[(item.wallet_id, item.token)].append(item)
        return {
            key: sorted(items, key=lambda row: (row.timestamp, row.id or 0))
            for key, items in grouped.items()
            if any(item.action.lower() in BUY_ACTIONS for item in items)
        }
