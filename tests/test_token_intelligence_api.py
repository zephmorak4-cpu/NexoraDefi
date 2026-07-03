from datetime import datetime, timezone

import httpx

from app.database.session import get_session
from app.main import app
from app.models import MomentumMetric, SmartMoneySignal, Token, TokenGrowthMetric


async def test_token_intelligence_api_endpoints(db_session):
    now = datetime.now(timezone.utc)
    token = Token(
        blockchain_address="0xapi-growth", symbol="GROW", name="Growth Token", chain="ethereum"
    )
    db_session.add(token)
    await db_session.flush()
    growth = TokenGrowthMetric(
        token_id=token.id, holder_count=100, holder_growth_24h=10, holder_growth_7d=50,
        transaction_count=200, transaction_growth_24h=20, transaction_growth_7d=80,
        volume_24h=100000, volume_growth_24h=30, volume_growth_7d=100,
        market_cap=1000000, market_cap_growth_24h=15, market_cap_growth_7d=60,
        liquidity_value=500000, liquidity_growth_24h=10, liquidity_growth_7d=40,
        calculated_at=now,
    )
    momentum = MomentumMetric(
        token_id=token.id, price_change_1h=2, price_change_24h=8,
        price_change_7d=20, price_change_30d=30, volatility_score=25,
        momentum_score=75, momentum_stage="TRENDING", calculated_at=now,
    )
    db_session.add_all([growth, momentum])
    await db_session.flush()
    signal = SmartMoneySignal(
        token_id=token.id, signal_type="ELITE_ENTRY", signal_strength=78,
        confidence_score=90, number_of_smart_wallets=3,
        total_capital_moved=250000, supporting_data_json={"momentum_stage": "TRENDING"},
        event_fingerprint="token-api-smart-money", created_at=now,
    )
    db_session.add(signal)
    await db_session.commit()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            growth_response = await client.get(f"/tokens/{token.id}/growth")
            momentum_response = await client.get(f"/tokens/{token.id}/momentum")
            trending = await client.get("/tokens/trending")
            watchlist = await client.get("/tokens/watchlist")
    finally:
        app.dependency_overrides.clear()

    assert growth_response.status_code == 200 and growth_response.json()["holder_count"] == 100
    assert momentum_response.status_code == 200
    assert momentum_response.json()["momentum_stage"] == "TRENDING"
    assert trending.status_code == 200 and trending.json()[0]["token_id"] == token.id
    assert watchlist.status_code == 200
    assert float(watchlist.json()[0]["signal_strength"]) == 78
    assert watchlist.json()[0]["signal_type"] == "ELITE_ENTRY"
