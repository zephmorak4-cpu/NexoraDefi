from datetime import datetime, timezone
from decimal import Decimal

import httpx

from app.database.session import get_session
from app.main import app
from app.models import SmartMoneySignal, Token, Wallet, WalletMetric, WalletPosition, WalletScore


async def test_smart_money_api_endpoints(db_session):
    now = datetime.now(timezone.utc)
    wallet = Wallet(wallet_address="0xranked", chain="ethereum")
    token = Token(blockchain_address="0xapi-token", symbol="API", name="API Token", chain="ethereum")
    db_session.add_all([wallet, token])
    await db_session.flush()
    db_session.add_all([
        WalletMetric(
            wallet_id=wallet.id, total_transactions=20, total_buys=15, total_sells=5,
            total_tokens_traded=2, estimated_total_profit=100, estimated_roi_percentage=20,
            average_return_percentage=15,
            average_holding_time_days=4, win_rate=75, loss_rate=25,
            largest_winner_percentage=30, largest_loss_percentage=-10, last_updated=now,
        ),
        WalletScore(
            wallet_id=wallet.id, profitability_score=80, consistency_score=75,
            risk_management_score=70, experience_score=60, recent_performance_score=85,
            final_smart_money_score=76, wallet_tier="ADVANCED", confidence_score=80,
            calculated_at=now,
        ),
        WalletPosition(
            wallet_id=wallet.id, token_id=token.id, total_bought_amount=10,
            total_sold_amount=2, current_balance=8, average_entry_price=5,
            realized_profit=2, unrealized_profit=8, first_purchase_date=now,
            latest_activity_date=now,
        ),
    ])
    await db_session.flush()
    db_session.add(SmartMoneySignal(
        token_id=token.id, signal_type="ACCUMULATION", signal_strength=80,
        confidence_score=75, number_of_smart_wallets=1, total_capital_moved=50,
        supporting_data_json={"wallet_ids": [wallet.id]}, event_fingerprint="api-signal",
        created_at=now,
    ))
    await db_session.commit()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            ranked = await client.get("/smart-money/wallets")
            profile = await client.get("/smart-money/wallets/0xranked")
            signals = await client.get("/smart-money/signals")
            top = await client.get("/smart-money/top-wallets")
            token_activity = await client.get(f"/smart-money/tokens/{token.id}")
    finally:
        app.dependency_overrides.clear()

    assert ranked.status_code == 200 and ranked.json()[0]["score"]["wallet_tier"] == "ADVANCED"
    assert profile.status_code == 200 and profile.json()["metrics"]["estimated_total_profit"] == "100.000000000000000000"
    assert signals.status_code == 200 and signals.json()[0]["signal_type"] == "ACCUMULATION"
    assert top.status_code == 200 and len(top.json()) == 1
    assert token_activity.status_code == 200 and len(token_activity.json()["positions"]) == 1
