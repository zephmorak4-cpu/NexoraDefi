from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.models import Alert, TokenQuality, TrackedWallet, WalletActivity
from app.smart_money.provider import BlockchainProvider, SolanaProvider
from app.smart_money.token_quality import TokenQualityEngine
from app.smart_money.wallet_reputation import clamp

logger = get_logger(__name__)


class SmartMoneySignalEngine:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        provider: BlockchainProvider | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.provider = provider or SolanaProvider(settings)

    async def generate(self) -> int:
        since = datetime.now(timezone.utc) - timedelta(minutes=self.settings.smart_money_monitor_window_minutes)
        rows = (
            await self.session.execute(
                select(WalletActivity, TrackedWallet)
                .join(TrackedWallet, TrackedWallet.id == WalletActivity.wallet_id)
                .where(WalletActivity.timestamp >= since, TrackedWallet.status == "active")
                .order_by(WalletActivity.timestamp.desc(), WalletActivity.id.desc())
            )
        ).all()
        generated = 0
        quality_engine = TokenQualityEngine(self.session, self.provider)
        for activity, wallet in rows:
            quality = await quality_engine.recalculate(activity.token_address, activity.token_symbol)
            conviction = await self.conviction_score(activity, wallet)
            if (
                Decimal(wallet.reputation_score) >= Decimal("85")
                and Decimal(quality.quality_score) >= Decimal("75")
                and conviction >= Decimal("80")
            ):
                generated += int(await self._create_alert(activity, wallet, quality, conviction))
        await self.session.commit()
        logger.info("solana_smart_money_signals_generated", signals=generated)
        return generated

    async def conviction_score(self, activity: WalletActivity, wallet: TrackedWallet) -> Decimal:
        repeat_count = await self.session.scalar(
            select(func.count(WalletActivity.id)).where(
                WalletActivity.wallet_id == wallet.id,
                WalletActivity.token_address == activity.token_address,
            )
        )
        aligned_wallets = await self.session.scalar(
            select(func.count(func.distinct(WalletActivity.wallet_id))).where(
                WalletActivity.token_address == activity.token_address
            )
        )
        position_size = clamp(Decimal(activity.usd_value or 0) / Decimal("500"))
        accumulation = position_size if activity.transaction_type not in {"sell", "out"} else Decimal("0")
        allocation = position_size
        repeat = clamp(Decimal(str(repeat_count or 0)) * Decimal("25"))
        alignment = Decimal("100") if Decimal(wallet.reputation_score) >= Decimal("85") else clamp(Decimal(str(aligned_wallets or 0)) * Decimal("25"))
        holding = Decimal("100") if activity.transaction_type not in {"sell", "out"} else Decimal("30")
        return clamp(
            position_size * Decimal("0.30")
            + accumulation * Decimal("0.20")
            + allocation * Decimal("0.20")
            + repeat * Decimal("0.10")
            + alignment * Decimal("0.10")
            + holding * Decimal("0.10")
        )

    async def _create_alert(
        self,
        activity: WalletActivity,
        wallet: TrackedWallet,
        quality: TokenQuality,
        conviction: Decimal,
    ) -> bool:
        fingerprint = f"solana:{activity.transaction_signature}:{activity.token_address}"
        exists = await self.session.scalar(select(Alert.id).where(Alert.alert_type == fingerprint))
        if exists:
            return False
        confidence = clamp((Decimal(wallet.reputation_score) + Decimal(quality.quality_score) + conviction) / Decimal("3"))
        self.session.add(
            Alert(
                alert_type=fingerprint,
                token_id=None,
                confidence_score=confidence,
                message=(
                    f"Solana Smart Money Alert\n"
                    f"Wallet: {wallet.wallet_label or wallet.wallet_name or wallet.wallet_address}\n"
                    f"Token: {activity.token_symbol} ({activity.token_address})\n"
                    f"Wallet Reputation: {wallet.reputation_score}\n"
                    f"Token Quality: {quality.quality_score}\n"
                    f"Conviction: {conviction}\n"
                    f"Confidence: {confidence}\n"
                    "Why It Matters: an elite tracked Solana wallet showed fresh activity before broad confirmation.\n"
                    "Risk Summary: this is an early signal, not a profit guarantee; verify liquidity and contract risk.\n"
                    "Suggested Action: add to watchlist and wait for confirmation before sizing any position."
                ),
            )
        )
        return True

    async def close(self) -> None:
        await self.provider.close()
