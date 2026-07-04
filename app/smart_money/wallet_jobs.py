from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import SessionFactory
from sqlalchemy import select

from app.models import WalletActivity
from app.smart_money.provider import SolanaProvider
from app.smart_money.token_quality import TokenQualityEngine
from app.smart_money.wallet_monitor import WalletMonitor
from app.smart_money.wallet_reputation import WalletReputationEngine
from app.smart_money.wallet_signals import SmartMoneySignalEngine

logger = get_logger(__name__)


async def monitor_solana_wallets() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        monitor = WalletMonitor(session, settings)
        try:
            return await monitor.monitor()
        except Exception:
            await session.rollback()
            logger.exception("solana_wallet_monitor_failed")
            raise
        finally:
            await monitor.close()


async def recalculate_solana_wallet_reputation() -> int:
    async with SessionFactory() as session:
        try:
            return await WalletReputationEngine(session).recalculate_all()
        except Exception:
            await session.rollback()
            logger.exception("solana_wallet_reputation_failed")
            raise


async def recalculate_solana_token_quality() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        provider = SolanaProvider(settings)
        try:
            activities = list((await session.scalars(select(WalletActivity))).all())
            engine = TokenQualityEngine(session, provider)
            seen: set[str] = set()
            count = 0
            for activity in activities:
                if activity.token_address in seen:
                    continue
                seen.add(activity.token_address)
                await engine.recalculate(activity.token_address, activity.token_symbol)
                count += 1
            await session.commit()
            return count
        except Exception:
            await session.rollback()
            logger.exception("solana_token_quality_failed")
            raise
        finally:
            await provider.close()


async def generate_solana_smart_money_signals() -> int:
    settings = get_settings()
    async with SessionFactory() as session:
        engine = SmartMoneySignalEngine(session, settings)
        try:
            return await engine.generate()
        except Exception:
            await session.rollback()
            logger.exception("solana_signal_generation_failed")
            raise
        finally:
            await engine.close()
