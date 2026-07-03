import httpx

from app.collectors.blockchain import BlockchainCollector
from app.collectors.market import MarketCollector
from app.collectors.social import SocialCollector
from app.core.config import Settings
from app.services.http import AsyncAPIClient


async def test_market_collector_fetches_and_stores(db_session):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{
            "id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "current_price": 65000,
            "market_cap": 1200000, "total_volume": 40000,
            "last_updated": "2023-11-14T22:13:20Z",
        }])

    http_client = httpx.AsyncClient(base_url="https://example.test", transport=httpx.MockTransport(handler))
    api_client = AsyncAPIClient("https://example.test", client=http_client)
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:", tracked_coins=["bitcoin"])
    collector = MarketCollector(db_session, settings, client=api_client)
    assert await collector.collect() == 1
    assert await collector.collect() == 0
    await http_client.aclose()


async def test_blockchain_collector_uses_moralis_token_transfers(db_session):
    wallet = "0xabc"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-Key"] == "test-moralis-key"
        assert request.url.path == f"/api/v2.2/{wallet}/erc20/transfers"
        return httpx.Response(200, json={
            "result": [{
                "transaction_hash": "0xhash",
                "log_index": "7",
                "from_address": "0xdef",
                "to_address": wallet,
                "value": "2500000000000000000",
                "token_decimals": "18",
                "token_symbol": "MOR",
                "token_name": "Moralis Token",
                "token_address": "0xtoken",
                "block_timestamp": "2026-07-03T10:00:00.000Z",
            }]
        })

    http_client = httpx.AsyncClient(base_url="https://deep-index.moralis.io", transport=httpx.MockTransport(handler))
    api_client = AsyncAPIClient("https://deep-index.moralis.io", client=http_client)
    settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        tracked_wallets=[wallet],
        moralis_api_key="test-moralis-key",
    )
    collector = BlockchainCollector(db_session, settings, moralis_client=api_client)

    assert await collector.collect() == 1
    assert await collector.collect() == 0
    await http_client.aclose()


def test_social_trending_topics():
    topics = SocialCollector.trending_topics([
        {"title": "Bitcoin bitcoin rally", "selftext": "Ethereum follows Bitcoin"}
    ])
    assert topics[0] == ("bitcoin", 3)
