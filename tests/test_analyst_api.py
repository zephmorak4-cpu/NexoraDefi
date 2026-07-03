import httpx

from app.database.session import get_session
from app.main import app
from tests.test_analyst_engine import seed_analyst_data


async def test_analyst_api_endpoints(db_session):
    token = await seed_analyst_data(db_session)

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            token_report = await client.get(f"/analyst/token/{token.id}?format=telegram")
            watchlist = await client.get("/analyst/watchlist")
            smart_money = await client.get("/analyst/smart-money")
    finally:
        app.dependency_overrides.clear()

    assert token_report.status_code == 200
    assert token_report.json()["format"] == "telegram"
    assert "*Token*" in token_report.json()["content"]
    assert watchlist.status_code == 200
    assert watchlist.json()[0]["report_type"] == "smart_money_alert"
    assert smart_money.status_code == 200
    assert smart_money.json()["report_type"] == "smart_money_summary"
