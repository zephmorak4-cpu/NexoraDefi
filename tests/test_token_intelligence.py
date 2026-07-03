from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.core.config import Settings
from app.models import (
    MomentumMetric,
    PriceHistory,
    SmartMoneySignal,
    Token,
    TokenGrowthMetric,
    Transaction,
    Wallet,
)
from app.services.token_intelligence import (
    MomentumAnalyzer,
    TokenGrowthAnalyzer,
    percentage_change,
)


async def create_token(db_session, suffix: str = "growth"):
    token = Token(
        blockchain_address=f"0x{suffix}", symbol=suffix[:6].upper(),
        name=suffix.title(), chain="ethereum",
    )
    db_session.add(token)
    await db_session.flush()
    return token


def test_holder_growth_calculation():
    assert percentage_change(150, 100) == Decimal("50.0")
    assert percentage_change(50, 100) == Decimal("-50.0")
    assert percentage_change(100, 0) == 0


async def test_incremental_growth_and_volume_calculations(db_session):
    token = await create_token(db_session)
    wallets = [Wallet(wallet_address=f"0xholder-{index}", chain="ethereum") for index in range(2)]
    db_session.add_all(wallets)
    await db_session.flush()
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    db_session.add_all([
        TokenGrowthMetric(
            token_id=token.id, holder_count=1, transaction_count=1,
            volume_24h=100, market_cap=1000, liquidity_value=500,
            calculated_at=now - timedelta(hours=24),
        ),
        TokenGrowthMetric(
            token_id=token.id, holder_count=1, transaction_count=1,
            volume_24h=50, market_cap=500, liquidity_value=250,
            calculated_at=now - timedelta(days=7),
        ),
        PriceHistory(
            token_id=token.id, price=2, market_cap=2000, volume=200,
            liquidity_value=1000, timestamp=now,
        ),
        *[
            Transaction(
                wallet_id=wallet.id, token_id=token.id, external_id=f"tx-{wallet.id}",
                transaction_type="buy", amount=1, price=2, timestamp=now - timedelta(hours=1),
            )
            for wallet in wallets
        ],
    ])
    await db_session.flush()

    metric = await TokenGrowthAnalyzer(db_session, Settings()).analyze_token(token.id, now)
    assert metric.holder_count == 2
    assert metric.holder_growth_24h == Decimal("100")
    assert metric.transaction_growth_24h == Decimal("100")
    assert metric.volume_growth_24h == Decimal("100")
    assert metric.liquidity_growth_7d == Decimal("300")
    assert TokenGrowthAnalyzer.growth_score(metric) > 80
    assert TokenGrowthAnalyzer.liquidity_score(metric) > 50

    duplicate = await TokenGrowthAnalyzer(db_session, Settings()).analyze_token(token.id, now)
    assert duplicate.id == metric.id


def test_momentum_classification():
    analyzer = MomentumAnalyzer(None, Settings())
    assert analyzer.classify_stage(5, 5, 5, 10, 10, 20, 1, 0) == "EARLY"
    assert analyzer.classify_stage(10, 12, 10, 20, 20, 20, 0, 0) == "ACCELERATING"
    assert analyzer.classify_stage(10, 20, 30, 10, 10, 20, 0, 0) == "TRENDING"
    assert analyzer.classify_stage(30, 40, 40, 100, 100, 20, 0, 0) == "OVERHEATED"
    assert analyzer.classify_stage(-5, -10, 5, -20, -10, 20, 0, 1) == "DECLINING"


async def test_momentum_analyzer_uses_historical_prices(db_session):
    token = await create_token(db_session, "momentum")
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    db_session.add_all([
        PriceHistory(token_id=token.id, price=50, timestamp=now - timedelta(days=30)),
        PriceHistory(token_id=token.id, price=70, timestamp=now - timedelta(days=7)),
        PriceHistory(token_id=token.id, price=80, timestamp=now - timedelta(hours=24)),
        PriceHistory(token_id=token.id, price=90, timestamp=now - timedelta(hours=1)),
        PriceHistory(token_id=token.id, price=100, timestamp=now),
        TokenGrowthMetric(
            token_id=token.id, holder_count=10, transaction_count=20,
            volume_growth_24h=100, transaction_growth_24h=50, calculated_at=now,
        ),
    ])
    await db_session.flush()

    metric = await MomentumAnalyzer(db_session, Settings()).analyze_token(token.id, now)
    assert metric.price_change_1h.quantize(Decimal("0.01")) == Decimal("11.11")
    assert metric.price_change_24h == Decimal("25.00")
    assert metric.price_change_30d == Decimal("100")
    assert metric.momentum_stage == "OVERHEATED"
