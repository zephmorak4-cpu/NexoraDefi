"""Solana Smart Money MVP acceptance checklist.

Executable tests live under ``tests/test_solana_smart_money.py``. This module is
kept as the package-level marker requested by the Solana MVP refactor prompt.
"""

ACCEPTANCE_CHECKS = (
    "curated_solana_wallets_are_managed_without_automatic_discovery",
    "wallet_monitor_records_provider_activity",
    "wallet_reputation_token_quality_and_conviction_gate_alerts",
    "telegram_can_deliver_generated_solana_alerts",
)
