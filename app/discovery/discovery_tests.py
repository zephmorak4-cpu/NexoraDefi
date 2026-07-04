"""Discovery acceptance marker.

Executable coverage lives in ``tests/test_discovery.py``.
"""

ACCEPTANCE_CHECKS = (
    "discovered_wallets_enter_candidate_pool",
    "candidate_wallets_do_not_emit_telegram_alerts",
    "candidate_scoring_is_weighted_and_configurable",
    "promotion_requires_observation_reputation_score_accuracy_and_low_suspicion",
    "demotion_returns_deteriorated_elite_wallets_to_observation",
)
