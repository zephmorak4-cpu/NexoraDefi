from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.collectors.blockchain import BlockchainCollector
from app.core.config import Settings
from app.models import Token, Wallet, WalletScore
from app.services.http import AsyncAPIClient
from app.services.wallet_discovery import WalletDiscoveryService


async def test_wallet_discovery_seeds_and_scores_wallets_from_token_transfers(db_session):
    token = Token(blockchain_address="0xdisc-token", symbol="DISC", name="Discovery", chain="ethereum")
    db_session.add(token)
    await db_session.flush()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v2.2/erc20/0xdisc-token/transfers"
        return httpx.Response(200, json={
            "result": [{
                "transaction_hash": "0xdisc-hash",
                "log_index": "1",
                "from_address": "0xsender",
                "to_address": "0xreceiver",
                "value": "1000000000000000000",
                "token_decimals": "18",
                "token_symbol": "DISC",
                "token_name": "Discovery",
                "token_address": "0xdisc-token",
                "block_timestamp": "2026-07-03T10:00:00.000Z",
            }]
        })

    http_client = httpx.AsyncClient(base_url="https://deep-index.moralis.io", transport=httpx.MockTransport(handler))
    api_client = AsyncAPIClient("https://deep-index.moralis.io", client=http_client)
    settings = Settings(
        moralis_api_key="test-key",
        wallet_discovery_min_transactions=1,
        wallet_discovery_batch_size=10,
    )
    service = WalletDiscoveryService(db_session, settings, moralis_client=api_client)

    assert await service.discover() == 4
    wallets = set(await db_session.scalars(select(Wallet.wallet_address)))
    assert wallets == {"0xsender", "0xreceiver"}
    scores = list((await db_session.scalars(select(WalletScore))).all())
    assert len(scores) == 2
    await http_client.aclose()


async def test_blockchain_collector_auto_tracks_scored_wallets(db_session):
    wallet = Wallet(wallet_address="0xauto", chain="ethereum")
    db_session.add(wallet)
    await db_session.flush()
    db_session.add(
        WalletScore(
            wallet_id=wallet.id,
            profitability_score=90,
            consistency_score=80,
            risk_management_score=80,
            experience_score=75,
            recent_performance_score=70,
            final_smart_money_score=82,
            wallet_tier="ADVANCED",
            confidence_score=90,
            calculated_at=datetime.now(timezone.utc),
        )
    )
    await db_session.flush()
    collector = BlockchainCollector(db_session, Settings(wallet_auto_track_threshold=75))

    assert await collector._wallets_to_collect() == ["0xauto"]
