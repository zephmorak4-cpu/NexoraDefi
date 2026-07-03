from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.config import Settings
from app.models import (
    MomentumMetric,
    PriceHistory,
    RiskEvent,
    SmartMoneySignal,
    Token,
    TokenGrowthMetric,
    TokenRiskMetric,
    Wallet,
    WalletPosition,
)
from app.services.risk import RiskAnalyzer, RiskEventDetector


async def create_token(db_session, suffix: str = "risk"):
    token = Token(
        blockchain_address=f"0x{suffix}", symbol=suffix[:6].upper(),
        name=suffix.title(), chain="ethereum",
    )
    db_session.add(token)
    await db_session.flush()
    return token


async def test_holder_concentration_uses_wallet_positions(db_session):
    token = await create_token(db_session, "holders")
    now = datetime.now(timezone.utc)
    wallets = [Wallet(wallet_address=f"0xholder-{index}", chain="ethereum") for index in range(12)]
    db_session.add_all(wallets)
    await db_session.flush()
    positions = [
        WalletPosition(
            wallet_id=wallet.id, token_id=token.id, total_bought_amount=amount,
            total_sold_amount=0, current_balance=amount, average_entry_price=1,
            realized_profit=0, unrealized_profit=0, first_purchase_date=now,
            latest_activity_date=now,
        )
        for wallet, amount in zip(wallets, [70, 10, 5, 3, 2, 2, 2, 2, 1, 1, 1, 1])
    ]
    db_session.add_all(positions)
    await db_session.flush()

    score, data = await RiskAnalyzer(db_session, Settings()).holder_distribution(token.id)
    assert score < 50
    assert Decimal(data["top10_holder_percentage"]) > 90


async def test_liquidity_and_volatility_risk_calculations(db_session):
    token = await create_token(db_session, "liqrisk")
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    db_session.add_all([
        TokenGrowthMetric(
            token_id=token.id, holder_count=100, transaction_count=50,
            liquidity_value=100000, liquidity_growth_24h=-40,
            liquidity_growth_7d=-10, calculated_at=now,
        ),
        MomentumMetric(
            token_id=token.id, price_change_1h=35, price_change_24h=80,
            price_change_7d=100, price_change_30d=120,
            volatility_score=85, momentum_score=50,
            momentum_stage="OVERHEATED", calculated_at=now,
        ),
    ])
    await db_session.flush()

    analyzer = RiskAnalyzer(db_session, Settings())
    liquidity_score, liquidity_data = await analyzer.liquidity(token.id)
    volatility_score, volatility_data = await analyzer.volatility(token.id, now)
    assert liquidity_score < 50
    assert liquidity_data["liquidity_growth_24h"] == "-40.0000"
    assert volatility_score == 0
    assert volatility_data["volatility_score"] == "85.0000"


async def test_smart_money_exit_and_contract_security_checks(db_session):
    token = await create_token(db_session, "exit")
    market_only = Token(symbol="MKT", name="Market Only", chain="market")
    db_session.add(market_only)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add(
        SmartMoneySignal(
            token_id=token.id, signal_type="SMART_MONEY_EXIT",
            signal_strength=90, confidence_score=90, number_of_smart_wallets=3,
            total_capital_moved=100000, supporting_data_json={},
            event_fingerprint="risk-exit", created_at=now,
        )
    )
    await db_session.flush()

    analyzer = RiskAnalyzer(db_session, Settings())
    exit_score, exit_data = await analyzer.smart_money_exit(token.id, now)
    contract_score, contract_data = await analyzer.contract_security(market_only.id)
    assert exit_score < 25
    assert exit_data["smart_wallets_exiting"] == 3
    assert contract_score == Decimal("50")
    assert contract_data["verification_status"] == "unavailable"


async def test_risk_scoring_and_event_generation(db_session):
    token = await create_token(db_session, "events")
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    db_session.add_all([
        TokenGrowthMetric(
            token_id=token.id, holder_count=5, transaction_count=10,
            liquidity_value=1000, liquidity_growth_24h=-50,
            liquidity_growth_7d=-50, calculated_at=now,
        ),
        MomentumMetric(
            token_id=token.id, price_change_1h=50, price_change_24h=100,
            price_change_7d=100, price_change_30d=100, volatility_score=90,
            momentum_score=20, momentum_stage="OVERHEATED", calculated_at=now,
        ),
        PriceHistory(token_id=token.id, price=1, timestamp=now),
        SmartMoneySignal(
            token_id=token.id, signal_type="SMART_MONEY_EXIT", signal_strength=95,
            confidence_score=90, number_of_smart_wallets=4, total_capital_moved=50000,
            supporting_data_json={}, event_fingerprint="risk-event-exit", created_at=now,
        ),
    ])
    await db_session.flush()

    analyzer = RiskAnalyzer(db_session, Settings())
    metric = await analyzer.analyze_token(token.id, now)
    assert metric.risk_level == "HIGH"
    assert metric.overall_risk_score < 60

    events = await RiskEventDetector(db_session, Settings()).detect_token(token.id, now)
    event_types = {event.event_type for event in events}
    assert {"LIQUIDITY_WARNING", "EXTREME_VOLATILITY", "SMART_MONEY_EXIT"} <= event_types
    duplicate_events = await RiskEventDetector(db_session, Settings()).detect_token(token.id, now)
    assert duplicate_events == []
    assert len((await db_session.scalars(select(RiskEvent))).all()) == len(events)


async def test_risk_analyzer_processes_all_tokens(db_session):
    first = await create_token(db_session, "allone")
    second = await create_token(db_session, "alltwo")
    now = datetime.now(timezone.utc)
    db_session.add_all([
        PriceHistory(token_id=first.id, price=1, timestamp=now - timedelta(days=10)),
        PriceHistory(token_id=second.id, price=1, timestamp=now - timedelta(days=10)),
    ])
    await db_session.flush()

    processed = await RiskAnalyzer(db_session, Settings(risk_batch_size=1)).analyze_all()
    assert processed == 2
    assert len((await db_session.scalars(select(TokenRiskMetric))).all()) == 2
