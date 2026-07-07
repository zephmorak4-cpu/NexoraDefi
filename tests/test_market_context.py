from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.config import Settings
from app.market_context.market_context import MarketContextEngine, explain_market_context
from app.models import CandidateWallet, MarketContext, PriceHistory, Token, TokenGrowthMetric, TrackedWallet, WalletActivity, WalletPosition
from app.trade_reconstruction.trade_reconstruction import TradeReconstructionEngine


async def test_market_context_scores_position_from_real_snapshots(db_session):
    now = datetime.now(timezone.utc)
    token = Token(
        blockchain_address="TokenContext",
        symbol="CTX",
        name="Context Token",
        chain="solana",
        created_at=now - timedelta(days=2),
    )
    wallet = CandidateWallet(wallet_address="context-wallet", chain="solana", discovery_reason="test", status="observing")
    elite = TrackedWallet(
        wallet_address="elite-wallet",
        chain="solana",
        status="active",
        reputation_score=Decimal("95"),
    )
    db_session.add_all([token, wallet, elite])
    await db_session.flush()
    entry = now - timedelta(hours=12)
    exit_time = now - timedelta(hours=1)
    db_session.add_all(
        [
            PriceHistory(token_id=token.id, price=Decimal("0.10"), market_cap=Decimal("100000"), volume=Decimal("50000"), liquidity_value=Decimal("25000"), timestamp=entry),
            PriceHistory(token_id=token.id, price=Decimal("0.25"), market_cap=Decimal("300000"), volume=Decimal("150000"), liquidity_value=Decimal("90000"), timestamp=exit_time),
            TokenGrowthMetric(token_id=token.id, holder_count=100, volume_24h=Decimal("50000"), market_cap=Decimal("100000"), liquidity_value=Decimal("25000"), calculated_at=entry),
            TokenGrowthMetric(token_id=token.id, holder_count=250, volume_24h=Decimal("150000"), market_cap=Decimal("300000"), liquidity_value=Decimal("90000"), calculated_at=exit_time),
            WalletActivity(
                wallet_id=elite.id,
                token_address="TokenContext",
                token_symbol="CTX",
                transaction_signature="elite-entry",
                transaction_type="buy",
                amount=Decimal("1"),
                usd_value=Decimal("1000"),
                timestamp=entry - timedelta(minutes=10),
            ),
            WalletPosition(
                candidate_wallet_id=wallet.id,
                token_address="TokenContext",
                entry_time=entry,
                final_exit_time=exit_time,
                average_entry_price=Decimal("0.10"),
                average_exit_price=Decimal("0.25"),
                current_balance=Decimal("0"),
                position_status="CLOSED",
                latest_activity_date=exit_time,
            ),
        ]
    )
    await db_session.commit()
    position = await db_session.scalar(select(WalletPosition))

    context = await MarketContextEngine(db_session, Settings()).enrich_position(position)
    await db_session.commit()

    assert context.market_cap_entry == Decimal("100000.00")
    assert context.liquidity_exit == Decimal("90000.00")
    assert context.holder_count_entry == 100
    assert context.holder_count_exit == 250
    assert context.context_score is not None
    assert "Elite before: 1" in context.wallet_consensus
    assert "supportive" in explain_market_context(context).lower() or "mixed" in explain_market_context(context).lower()


async def test_market_context_keeps_missing_market_data_null(db_session):
    wallet = CandidateWallet(wallet_address="missing-context-wallet", chain="solana", discovery_reason="test", status="observing")
    db_session.add(wallet)
    await db_session.flush()
    position = WalletPosition(
        candidate_wallet_id=wallet.id,
        token_address="MissingToken",
        entry_time=datetime.now(timezone.utc) - timedelta(days=1),
        average_entry_price=Decimal("1"),
        current_balance=Decimal("1"),
        position_status="OPEN",
        latest_activity_date=datetime.now(timezone.utc),
    )
    db_session.add(position)
    await db_session.commit()

    context = await MarketContextEngine(db_session, Settings()).enrich_position(position)

    assert context.market_cap_entry is None
    assert context.liquidity_entry is None
    assert context.holder_count_entry is None
    assert context.context_score is None
    assert context.market_sentiment == "Insufficient Market Data"
    assert explain_market_context(context) == "Insufficient Market Data"


async def test_trade_reconstruction_creates_market_context_rows(db_session):
    wallet = CandidateWallet(
        wallet_address="rebuild-context-wallet",
        chain="solana",
        discovery_reason="test",
        status="observing",
    )
    db_session.add(wallet)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    from app.models import CandidateHistory

    db_session.add_all(
        [
            CandidateHistory(wallet_id=wallet.id, signature="buy", token="RebuildToken", action="buy", amount=Decimal("10"), usd_value=Decimal("100"), timestamp=now - timedelta(days=2)),
            CandidateHistory(wallet_id=wallet.id, signature="sell", token="RebuildToken", action="sell", amount=Decimal("10"), usd_value=Decimal("200"), timestamp=now - timedelta(days=1)),
        ]
    )
    await db_session.commit()

    rebuilt = await TradeReconstructionEngine(db_session).rebuild_wallet(wallet.id)
    context = await db_session.scalar(select(MarketContext))

    assert rebuilt == 1
    assert context is not None
    assert context.token_address == "RebuildToken"
    assert context.context_score is None
