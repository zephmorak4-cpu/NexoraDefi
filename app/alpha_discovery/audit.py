ALPHA_DISCOVERY_AUDIT = {
    "mode": "alert_only",
    "new_modules": [
        "app.alpha_discovery.agents",
        "app.alpha_discovery.engine",
        "app.alpha_discovery.services",
        "app.alpha_discovery.format_alert",
        "app.alpha_discovery.jobs",
        "app.alpha_discovery.api",
    ],
    "new_tables": [
        "alpha_scanned_tokens",
        "alpha_alert_history",
        "alpha_watchlist_tokens",
        "alpha_smart_wallets",
    ],
    "preserved_workflows": [
        "wallet discovery",
        "wallet intelligence reports",
        "trade reconstruction",
        "cost basis enrichment",
        "risk intelligence",
        "analyst reporting",
        "telegram notifications",
    ],
    "safety_boundaries": [
        "no private key handling",
        "no auto-buy execution",
        "no auto-sell execution",
        "no swap or order placement",
        "manual review required before any user action",
    ],
}
