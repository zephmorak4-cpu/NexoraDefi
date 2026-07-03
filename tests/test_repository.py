from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import PriceHistory, Token
from app.schemas.records import PriceRecord
from app.services.repository import DataRepository


async def test_duplicate_price_is_prevented(db_session):
    repository = DataRepository(db_session)
    record = PriceRecord(
        coin_id="bitcoin", symbol="BTC", name="Bitcoin", price=Decimal("100"),
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    assert await repository.add_price(record) is True
    await db_session.flush()
    assert await repository.add_price(record) is False


async def test_market_data_links_unique_onchain_symbol(db_session):
    token = Token(
        blockchain_address="0xbtc", symbol="BTC", name="Wrapped Bitcoin", chain="ethereum"
    )
    db_session.add(token)
    await db_session.flush()
    repository = DataRepository(db_session)
    record = PriceRecord(
        coin_id="bitcoin", symbol="BTC", name="Bitcoin", price=Decimal("100"),
        timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc),
    )
    assert await repository.add_price(record) is True
    await db_session.flush()
    price = await db_session.scalar(select(PriceHistory))
    assert price.token_id == token.id
    assert token.category == "bitcoin"
