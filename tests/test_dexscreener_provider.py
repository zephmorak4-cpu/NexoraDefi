from decimal import Decimal

import httpx

from app.core.config import Settings
from app.services.http import AsyncAPIClient
from app.smart_money.provider import SolanaProvider


async def test_solana_provider_reads_dexscreener_tokens_v1_market_data():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/tokens/v1/solana/TokenMint"
        return httpx.Response(
            200,
            json=[
                {
                    "chainId": "solana",
                    "baseToken": {"address": "TokenMint", "symbol": "TKN"},
                    "liquidity": {"usd": 250000},
                    "volume": {"h24": 1000000},
                    "marketCap": 5000000,
                    "pairCreatedAt": 1783000000000,
                }
            ],
        )

    http_client = httpx.AsyncClient(base_url="https://api.dexscreener.com", transport=httpx.MockTransport(handler))
    dexscreener = AsyncAPIClient("https://api.dexscreener.com", client=http_client)
    provider = SolanaProvider(Settings(), dexscreener_client=dexscreener)

    data = await provider.token_market_data("TokenMint")

    assert data.token_symbol == "TKN"
    assert data.liquidity_usd == Decimal("250000")
    assert data.volume_24h_usd == Decimal("1000000")
    assert data.market_cap_usd == Decimal("5000000")
    await provider.close()


async def test_solana_provider_falls_back_to_dexscreener_token_pairs():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/tokens/v1/solana/TokenMint":
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json=[
                {
                    "chainId": "solana",
                    "baseToken": {"address": "TokenMint", "symbol": "PAIR"},
                    "liquidity": {"usd": 75000},
                    "volume": {"h24": 150000},
                    "fdv": 900000,
                }
            ],
        )

    http_client = httpx.AsyncClient(base_url="https://api.dexscreener.com", transport=httpx.MockTransport(handler))
    dexscreener = AsyncAPIClient("https://api.dexscreener.com", client=http_client)
    provider = SolanaProvider(Settings(), dexscreener_client=dexscreener)

    data = await provider.token_market_data("TokenMint")

    assert paths == ["/tokens/v1/solana/TokenMint", "/token-pairs/v1/solana/TokenMint"]
    assert data.token_symbol == "PAIR"
    assert data.market_cap_usd == Decimal("900000")
    await provider.close()
