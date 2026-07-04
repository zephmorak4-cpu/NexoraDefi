from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.config import Settings
from app.models import Alert, TokenQuality, TrackedWallet, WalletActivity
from app.smart_money.provider import BlockchainProvider, TokenMarketData, WalletTransfer
from app.smart_money.token_quality import TokenQualityEngine
from app.smart_money.tracked_wallets import TrackedWalletManager
from app.smart_money.wallet_monitor import WalletMonitor
from app.smart_money.wallet_reputation import WalletReputationEngine
from app.smart_money.wallet_signals import SmartMoneySignalEngine


class FakeSolanaProvider(BlockchainProvider):
    chain = "solana"

    async def wallet_transfers(self, wallet_address: str, limit: int = 50) -> list[WalletTransfer]:
        return [
            WalletTransfer(
                signature="sig-1",
                token_address="Token111111111111111111111111111111111111111",
                token_symbol="TKN",
                transaction_type="buy",
                amount=Decimal("100"),
                usd_value=Decimal("50000"),
                timestamp=datetime.now(timezone.utc),
            )
        ]

    async def token_market_data(self, token_address: str, token_symbol: str = "UNKNOWN") -> TokenMarketData:
        return TokenMarketData(
            token_address=token_address,
            token_symbol=token_symbol,
            liquidity_usd=Decimal("200000"),
            volume_24h_usd=Decimal("500000"),
            market_cap_usd=Decimal("2000000"),
            age_hours=Decimal("100"),
            holder_count=2000,
            risk_flags=0,
        )

    async def close(self) -> None:
        return None


async def test_tracked_wallet_manager_adds_and_removes_solana_wallet(db_session):
    manager = TrackedWalletManager(db_session)
    wallet = await manager.add_wallet("sol-wallet", wallet_label="Elite", notes="curated")

    assert wallet.chain == "solana"
    assert wallet.status == "active"
    assert await manager.remove_wallet("sol-wallet")
    assert (await db_session.scalar(select(TrackedWallet))).status == "removed"


async def test_wallet_monitor_records_provider_activity(db_session):
    await TrackedWalletManager(db_session).add_wallet("sol-wallet")
    monitor = WalletMonitor(db_session, Settings(), provider=FakeSolanaProvider())

    assert await monitor.monitor() == 1
    assert await monitor.monitor() == 0
    activity = await db_session.scalar(select(WalletActivity))
    assert activity.token_symbol == "TKN"


async def test_reputation_quality_and_signal_generation(db_session):
    wallet = await TrackedWalletManager(db_session).add_wallet("sol-wallet")
    db_session.add(
        WalletActivity(
            wallet_id=wallet.id,
            token_address="Token111111111111111111111111111111111111111",
            token_symbol="TKN",
            transaction_signature="sig-1",
            transaction_type="buy",
            amount=Decimal("100"),
            usd_value=Decimal("50000"),
            timestamp=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    wallet.reputation_score = Decimal("90")
    quality = await TokenQualityEngine(db_session, FakeSolanaProvider()).recalculate(
        "Token111111111111111111111111111111111111111",
        "TKN",
    )
    await db_session.commit()
    assert quality.quality_score >= Decimal("75")

    generated = await SmartMoneySignalEngine(db_session, Settings(), provider=FakeSolanaProvider()).generate()
    assert generated == 1
    assert (await db_session.scalar(select(Alert))).alert_type.startswith("solana:")

    reputation = await WalletReputationEngine(db_session).score_wallet(wallet.id)
    assert reputation > 0
