from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.config import Settings
from app.models import (
    SmartMoneySignal,
    Token,
    Transaction,
    Wallet,
    WalletMetric,
    WalletPosition,
    WalletScore,
)
from app.services.smart_money import SmartMoneyDetector, SmartMoneyScorer, WalletAnalyzer


async def create_wallet_and_token(db_session, address: str = "0xwallet"):
    wallet = Wallet(wallet_address=address, chain="ethereum")
    token = Token(blockchain_address=f"0xtoken-{address}", symbol="TKN", name="Token", chain="ethereum")
    db_session.add_all([wallet, token])
    await db_session.flush()
    return wallet, token


async def test_wallet_profit_and_roi_calculations(db_session):
    wallet, token = await create_wallet_and_token(db_session)
    now = datetime.now(timezone.utc)
    db_session.add_all([
        Transaction(
            wallet_id=wallet.id, token_id=token.id, external_id="buy", transaction_type="buy",
            amount=Decimal("100"), price=Decimal("10"), timestamp=now - timedelta(days=10),
        ),
        Transaction(
            wallet_id=wallet.id, token_id=token.id, external_id="sell", transaction_type="sell",
            amount=Decimal("40"), price=Decimal("15"), timestamp=now,
        ),
    ])
    await db_session.flush()

    metric = await WalletAnalyzer(db_session, Settings()).analyze_wallet(wallet.id)
    position = await db_session.scalar(
        select(WalletPosition).where(WalletPosition.wallet_id == wallet.id)
    )

    assert position.current_balance == Decimal("60")
    assert position.average_entry_price == Decimal("10")
    assert position.realized_profit == Decimal("200")
    assert position.unrealized_profit == Decimal("300")
    assert metric.estimated_total_profit == Decimal("500")
    assert metric.estimated_roi_percentage == Decimal("50")
    assert metric.average_return_percentage == Decimal("50")
    assert metric.total_buys == 1
    assert metric.total_sells == 1

    await WalletAnalyzer(db_session, Settings()).analyze_wallet(wallet.id)
    assert metric.total_transactions == 2


def test_scoring_accuracy_and_tier_classification():
    settings = Settings()
    scorer = SmartMoneyScorer(None, settings)
    components = {
        "profitability": Decimal("100"),
        "consistency": Decimal("80"),
        "risk_management": Decimal("60"),
        "experience": Decimal("40"),
        "recent_performance": Decimal("20"),
    }
    assert scorer.final_score(components) == Decimal("75.0000")
    assert scorer.classify_tier(Decimal("90")) == "ELITE"
    assert scorer.classify_tier(Decimal("75")) == "ADVANCED"
    assert scorer.classify_tier(Decimal("60")) == "INTERMEDIATE"
    assert scorer.classify_tier(Decimal("40")) == "SPECULATIVE"
    assert scorer.classify_tier(Decimal("39.99")) == "LOW_QUALITY"


def test_signal_confidence_scoring():
    confidence = SmartMoneyDetector.confidence_score(
        average_wallet_quality=Decimal("90"),
        participating_wallets=3,
        position_size_score=Decimal("80"),
        historical_success=Decimal("70"),
        recency_score=Decimal("100"),
    )
    assert confidence == Decimal("88.00")


async def test_elite_entry_signal_generation_and_deduplication(db_session):
    wallet, new_token = await create_wallet_and_token(db_session)
    history_token = Token(
        blockchain_address="0xhistory", symbol="OLD", name="Old Token", chain="ethereum"
    )
    db_session.add(history_token)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    history = Transaction(
        wallet_id=wallet.id, token_id=history_token.id, external_id="history", transaction_type="buy",
        amount=Decimal("10"), price=Decimal("1"), timestamp=now - timedelta(hours=2),
    )
    entry = Transaction(
        wallet_id=wallet.id, token_id=new_token.id, external_id="entry", transaction_type="buy",
        amount=Decimal("20"), price=Decimal("2"), timestamp=now - timedelta(minutes=1),
    )
    db_session.add_all([history, entry])
    await db_session.flush()
    db_session.add_all([
        WalletMetric(
            wallet_id=wallet.id, total_transactions=100, total_buys=80, total_sells=20,
            total_tokens_traded=10, win_rate=Decimal("80"), loss_rate=Decimal("20"),
        ),
        WalletPosition(
            wallet_id=wallet.id, token_id=new_token.id, total_bought_amount=Decimal("20"),
            total_sold_amount=0, current_balance=Decimal("20"), average_entry_price=Decimal("2"),
            realized_profit=0, unrealized_profit=0, first_purchase_date=entry.timestamp,
            latest_activity_date=entry.timestamp,
        ),
        WalletScore(
            wallet_id=wallet.id, profitability_score=85, consistency_score=80,
            risk_management_score=75, experience_score=70, recent_performance_score=90,
            final_smart_money_score=80, wallet_tier="ADVANCED", confidence_score=90,
            calculated_at=now,
        ),
    ])
    await db_session.flush()
    detector = SmartMoneyDetector(db_session, Settings())

    assert await detector.detect(now) == 1
    signal = await db_session.scalar(select(SmartMoneySignal))
    assert signal.signal_type == "ELITE_ENTRY"
    assert signal.token_id == new_token.id
    assert signal.total_capital_moved == Decimal("40")
    assert await detector.detect(now) == 0


async def test_accumulation_cluster_and_exit_signals(db_session):
    now = datetime.now(timezone.utc)
    accumulation_token = Token(
        blockchain_address="0xacc", symbol="ACC", name="Accumulation", chain="ethereum"
    )
    cluster_token = Token(
        blockchain_address="0xcluster", symbol="CLU", name="Cluster", chain="ethereum"
    )
    exit_token = Token(
        blockchain_address="0xexit", symbol="EXT", name="Exit", chain="ethereum"
    )
    wallets = [Wallet(wallet_address=f"0xsmart-{index}", chain="ethereum") for index in range(4)]
    db_session.add_all([accumulation_token, cluster_token, exit_token, *wallets])
    await db_session.flush()
    for wallet in wallets:
        db_session.add_all([
            WalletMetric(
                wallet_id=wallet.id, total_transactions=100, total_buys=70, total_sells=30,
                total_tokens_traded=10, win_rate=75, loss_rate=25,
            ),
            WalletScore(
                wallet_id=wallet.id, profitability_score=85, consistency_score=80,
                risk_management_score=75, experience_score=70, recent_performance_score=85,
                final_smart_money_score=80, wallet_tier="ADVANCED", confidence_score=90,
                calculated_at=now,
            ),
        ])
    accumulation = Transaction(
        wallet_id=wallets[0].id, token_id=accumulation_token.id, external_id="acc",
        transaction_type="buy", amount=20, price=2, timestamp=now - timedelta(hours=1),
    )
    exit_transaction = Transaction(
        wallet_id=wallets[0].id, token_id=exit_token.id, external_id="exit",
        transaction_type="sell", amount=60, price=3, timestamp=now - timedelta(minutes=1),
    )
    cluster_transactions = [
        Transaction(
            wallet_id=wallet.id, token_id=cluster_token.id, external_id=f"cluster-{wallet.id}",
            transaction_type="buy", amount=1, price=5, timestamp=now - timedelta(hours=1),
        )
        for wallet in wallets[1:]
    ]
    db_session.add_all([accumulation, exit_transaction, *cluster_transactions])
    await db_session.flush()
    db_session.add_all([
        WalletPosition(
            wallet_id=wallets[0].id, token_id=accumulation_token.id, total_bought_amount=100,
            total_sold_amount=0, current_balance=100, average_entry_price=2,
            realized_profit=0, unrealized_profit=0, first_purchase_date=now - timedelta(days=3),
            latest_activity_date=accumulation.timestamp,
        ),
        WalletPosition(
            wallet_id=wallets[0].id, token_id=exit_token.id, total_bought_amount=100,
            total_sold_amount=60, current_balance=40, average_entry_price=2,
            realized_profit=60, unrealized_profit=40, first_purchase_date=now - timedelta(days=5),
            latest_activity_date=exit_transaction.timestamp,
        ),
        *[
            WalletPosition(
                wallet_id=wallet.id, token_id=cluster_token.id, total_bought_amount=100,
                total_sold_amount=0, current_balance=100, average_entry_price=5,
                realized_profit=0, unrealized_profit=0, first_purchase_date=now - timedelta(days=2),
                latest_activity_date=now - timedelta(hours=1),
            )
            for wallet in wallets[1:]
        ],
    ])
    await db_session.flush()

    assert await SmartMoneyDetector(db_session, Settings()).detect(now) == 3
    signal_types = set(await db_session.scalars(select(SmartMoneySignal.signal_type)))
    assert signal_types == {"ACCUMULATION", "SMART_MONEY_CLUSTER", "SMART_MONEY_EXIT"}
