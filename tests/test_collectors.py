import httpx

from datetime import datetime, timezone
from decimal import Decimal

from app.collectors.blockchain import BlockchainCollector
from app.collectors.market import MarketCollector
from app.collectors.social import SocialCollector
from app.core.config import Settings
from app.models import TrackedWallet
from app.services.http import AsyncAPIClient
from app.smart_money.provider import BlockchainProvider, TokenMarketData, WalletTransfer


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


class FakeSolanaProvider(BlockchainProvider):
    chain = "solana"

    async def wallet_transfers(self, wallet_address: str, limit: int = 50) -> list[WalletTransfer]:
        return [
            WalletTransfer(
                signature="solsig",
                token_address="So11111111111111111111111111111111111111112",
                token_symbol="SOL",
                transaction_type="buy",
                amount=Decimal("2.5"),
                usd_value=Decimal("500"),
                timestamp=datetime.now(timezone.utc),
            )
        ]

    async def token_market_data(self, token_address: str, token_symbol: str = "UNKNOWN") -> TokenMarketData:
        return TokenMarketData(token_address=token_address, token_symbol=token_symbol)

    async def close(self) -> None:
        return None


async def test_blockchain_collector_monitors_solana_tracked_wallets(db_session):
    db_session.add(TrackedWallet(wallet_address="sol-wallet", chain="solana", status="active"))
    await db_session.flush()
    settings = Settings(database_url="sqlite+aiosqlite:///:memory:")
    collector = BlockchainCollector(db_session, settings, provider=FakeSolanaProvider())

    assert await collector.collect() == 1
    assert await collector.collect() == 0


def test_social_trending_topics():
    topics = SocialCollector.trending_topics([
        {"title": "Bitcoin bitcoin rally", "selftext": "Ethereum follows Bitcoin"}
    ])
    assert topics[0] == ("bitcoin", 3)
