from collections.abc import Callable
from typing import Any

from app.analyst.analyst_jobs import generate_analyst_reports
from app.collectors import BlockchainCollector, MarketCollector, NewsCollector, SocialCollector
from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import SessionFactory
from app.services.risk import RiskAnalyzer, RiskEventDetector
from app.services.smart_money import SmartMoneyDetector, SmartMoneyScorer, WalletAnalyzer
from app.services.token_intelligence import MomentumAnalyzer, TokenGrowthAnalyzer
from app.telegram.notifier import TelegramNotifier

logger = get_logger(__name__)


async def run_collector(collector_type: Callable[..., Any]) -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        collector = collector_type(session, settings)
        try:
            return await collector.collect()
        except Exception:
            await session.rollback()
            logger.exception("scheduled_collector_failed", collector=collector_type.__name__)
            raise
        finally:
            await collector.close()


async def refresh_blockchain() -> int:
    return await run_collector(BlockchainCollector)


async def refresh_market() -> int:
    return await run_collector(MarketCollector)


async def refresh_social() -> int:
    return await run_collector(SocialCollector)


async def refresh_news() -> int:
    return await run_collector(NewsCollector)


async def analyze_wallets() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        try:
            return await WalletAnalyzer(session, settings).analyze_all()
        except Exception:
            await session.rollback()
            logger.exception("wallet_analysis_failed")
            raise


async def recalculate_wallet_scores() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        try:
            return await SmartMoneyScorer(session, settings).score_all()
        except Exception:
            await session.rollback()
            logger.exception("wallet_scoring_failed")
            raise


async def generate_smart_money_signals() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        try:
            return await SmartMoneyDetector(session, settings).detect()
        except Exception:
            await session.rollback()
            logger.exception("smart_money_detection_failed")
            raise


async def analyze_token_growth() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        try:
            return await TokenGrowthAnalyzer(session, settings).analyze_all()
        except Exception:
            await session.rollback()
            logger.exception("token_growth_analysis_failed")
            raise


async def analyze_token_momentum() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        try:
            return await MomentumAnalyzer(session, settings).analyze_all()
        except Exception:
            await session.rollback()
            logger.exception("token_momentum_analysis_failed")
            raise


async def detect_rapid_token_changes() -> int:
    return await analyze_token_momentum()


async def update_risk_volatility() -> int:
    return await analyze_token_momentum()


async def recalculate_token_risk_scores() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        try:
            return await RiskAnalyzer(session, settings).analyze_all()
        except Exception:
            await session.rollback()
            logger.exception("risk_analysis_failed")
            raise


async def detect_critical_risk_events() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        try:
            return await RiskEventDetector(session, settings).detect_all()
        except Exception:
            await session.rollback()
            logger.exception("risk_event_detection_failed")
            raise


async def send_smart_money_alerts() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        notifier = TelegramNotifier(session, settings)
        try:
            return await notifier.send_recent_smart_money_alerts()
        except Exception:
            await session.rollback()
            logger.exception("telegram_smart_money_alerts_failed")
            raise
        finally:
            await notifier.close()


async def send_daily_summary() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        notifier = TelegramNotifier(session, settings)
        try:
            return await notifier.send_daily_summary()
        except Exception:
            await session.rollback()
            logger.exception("telegram_daily_summary_failed")
            raise
        finally:
            await notifier.close()
