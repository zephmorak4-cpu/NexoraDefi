from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import Settings
from app.jobs.tasks import (
    analyze_wallets,
    analyze_token_growth,
    analyze_token_momentum,
    detect_rapid_token_changes,
    detect_critical_risk_events,
    discover_wallets,
    generate_analyst_reports,
    generate_smart_money_signals,
    recalculate_token_risk_scores,
    recalculate_wallet_scores,
    refresh_blockchain,
    refresh_market,
    refresh_news,
    refresh_social,
    send_daily_summary,
    send_smart_money_alerts,
    update_risk_volatility,
)


def build_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    jobs = (
        (refresh_blockchain, "blockchain", settings.blockchain_refresh_seconds),
        (refresh_market, "market", settings.market_refresh_seconds),
        (refresh_social, "social", settings.social_refresh_seconds),
        (refresh_news, "news", settings.news_refresh_seconds),
        (analyze_wallets, "wallet_analysis", settings.wallet_analysis_interval_seconds),
        (recalculate_wallet_scores, "wallet_scoring", settings.wallet_scoring_interval_seconds),
        (discover_wallets, "wallet_discovery", settings.wallet_discovery_interval_seconds),
        (generate_smart_money_signals, "smart_money_signals", settings.smart_money_signal_interval_seconds),
        (detect_rapid_token_changes, "token_rapid_changes", settings.token_rapid_change_interval_seconds),
        (analyze_token_growth, "token_growth", settings.token_growth_interval_seconds),
        (analyze_token_momentum, "token_momentum", settings.token_momentum_interval_seconds),
        (update_risk_volatility, "risk_volatility", settings.risk_volatility_interval_seconds),
        (recalculate_token_risk_scores, "risk_scores", settings.risk_score_interval_seconds),
        (detect_critical_risk_events, "risk_events", settings.risk_event_interval_seconds),
        (generate_analyst_reports, "analyst_reports", settings.analyst_report_interval_seconds),
        (send_smart_money_alerts, "telegram_smart_money_alerts", settings.telegram_alert_interval_seconds),
        (send_daily_summary, "telegram_daily_summary", settings.telegram_daily_summary_interval_seconds),
    )
    for task, job_id, seconds in jobs:
        scheduler.add_job(
            task,
            "interval",
            seconds=seconds,
            id=job_id,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=max(seconds, 30),
        )
    return scheduler
