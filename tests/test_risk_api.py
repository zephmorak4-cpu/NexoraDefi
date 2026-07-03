from datetime import datetime, timezone

import httpx

from app.database.session import get_session
from app.main import app
from app.models import RiskEvent, Token, TokenRiskMetric


async def test_risk_api_endpoints(db_session):
    now = datetime.now(timezone.utc)
    token = Token(blockchain_address="0xriskapi", symbol="RISK", name="Risk Token", chain="ethereum")
    db_session.add(token)
    await db_session.flush()
    metric = TokenRiskMetric(
        token_id=token.id, holder_concentration_score=40,
        liquidity_risk_score=35, volatility_risk_score=25,
        age_risk_score=30, smart_money_exit_risk_score=20,
        contract_security_score=60, overall_risk_score=34,
        risk_level="HIGH", calculated_at=now,
    )
    low_metric = TokenRiskMetric(
        token_id=token.id, holder_concentration_score=95,
        liquidity_risk_score=90, volatility_risk_score=90,
        age_risk_score=95, smart_money_exit_risk_score=100,
        contract_security_score=80, overall_risk_score=92,
        risk_level="LOW", calculated_at=now,
    )
    event = RiskEvent(
        token_id=token.id, event_type="EXTREME_VOLATILITY",
        severity="HIGH", confidence_score=90,
        description="Observed price movement exceeded configured volatility risk thresholds.",
        supporting_data_json={"volatility_score": "90"},
        created_at=now,
    )
    db_session.add_all([metric, low_metric, event])
    await db_session.commit()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            token_risk = await client.get(f"/risk/tokens/{token.id}")
            events = await client.get("/risk/events")
            high_risk = await client.get("/risk/high-risk")
            low_risk = await client.get("/risk/low-risk")
    finally:
        app.dependency_overrides.clear()

    assert token_risk.status_code == 200
    assert token_risk.json()["risk_factors"]["contract_security"]["verification_status"] == "unknown_free_source"
    assert events.status_code == 200
    assert events.json()[0]["event_type"] == "EXTREME_VOLATILITY"
    assert high_risk.status_code == 200 and high_risk.json() == []
    assert low_risk.status_code == 200
    assert float(low_risk.json()[0]["overall_risk_score"]) == 92
