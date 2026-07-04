from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.core.config import Settings
from app.discovery import discovery_api
from app.discovery.candidate_scoring import CandidateScoringEngine
from app.discovery.candidate_wallet import DiscoveryEvent
from app.discovery.discovery_engine import DiscoveryEngine
from app.discovery.wallet_classifier import WalletClassifier
from app.discovery.wallet_promotion import WalletPromotionService
from app.main import app
from app.models import CandidateHistory, CandidateWallet, TokenQuality, TrackedWallet


class FakeDiscoverySource:
    async def events(self) -> list[DiscoveryEvent]:
        now = datetime.now(timezone.utc)
        return [
            DiscoveryEvent(
                wallet_address="candidate-sol-wallet",
                token="TokenMint",
                action="swap",
                amount=Decimal("100"),
                usd_value=Decimal("25000"),
                timestamp=now,
                reason="large_dex_swap",
            )
        ]

    async def close(self) -> None:
        return None


async def test_discovery_engine_adds_candidate_without_tracking_or_alerting(db_session):
    discovered = await DiscoveryEngine(db_session, Settings(), source=FakeDiscoverySource()).discover()

    candidate = await db_session.scalar(select(CandidateWallet))
    assert discovered == 1
    assert candidate.wallet_address == "candidate-sol-wallet"
    assert candidate.status == "observing"
    assert await db_session.scalar(select(TrackedWallet)) is None


async def test_candidate_scoring_and_classification(db_session):
    candidate = CandidateWallet(
        wallet_address="candidate-sol-wallet",
        chain="solana",
        discovery_reason="large_purchases",
        status="observing",
    )
    db_session.add(candidate)
    await db_session.flush()
    db_session.add_all(
        [
            CandidateHistory(
                wallet_id=candidate.id,
                token="TokenMint",
                action="liquidity_add",
                amount=Decimal("10"),
                usd_value=Decimal("50000"),
                timestamp=datetime.now(timezone.utc) - timedelta(days=1),
            ),
            CandidateHistory(
                wallet_id=candidate.id,
                token="TokenMint",
                action="liquidity_add",
                amount=Decimal("12"),
                usd_value=Decimal("60000"),
                timestamp=datetime.now(timezone.utc),
            ),
        ]
    )
    db_session.add(TokenQuality(token_address="TokenMint", token_symbol="TKN", quality_score=90))
    await db_session.commit()

    assert WalletClassifier().classify(await discovery_api.WalletHistoryService(db_session).for_candidate(candidate.id)) == "Liquidity Provider"
    assert await CandidateScoringEngine(db_session, Settings()).score_all() == 1

    refreshed = await db_session.get(CandidateWallet, candidate.id)
    assert refreshed.candidate_score >= 60
    assert refreshed.reputation_score > 0


async def test_promotion_and_demotion_lifecycle(db_session):
    candidate = CandidateWallet(
        wallet_address="candidate-sol-wallet",
        chain="solana",
        first_seen=datetime.now(timezone.utc) - timedelta(days=10),
        discovery_reason="consistent_large_swaps",
        wallet_type="Whale",
        candidate_score=90,
        reputation_score=88,
        historical_accuracy_score=80,
        suspicious_score=0,
        status="observing",
    )
    db_session.add(candidate)
    await db_session.commit()

    service = WalletPromotionService(db_session, Settings(candidate_observation_days=7))
    assert await service.evaluate_promotions() == 1
    tracked = await db_session.scalar(select(TrackedWallet))
    assert tracked.wallet_address == "candidate-sol-wallet"
    assert tracked.status == "active"

    tracked.reputation_score = Decimal("10")
    await db_session.commit()
    assert await service.evaluate_demotions() == 1
    assert tracked.status == "observing"


async def test_discovery_admin_api_lists_candidates(db_session, monkeypatch):
    db_session.add(
        CandidateWallet(
            wallet_address="candidate-sol-wallet",
            chain="solana",
            discovery_reason="large_token_purchase",
            status="observing",
        )
    )
    await db_session.commit()

    @asynccontextmanager
    async def fake_session_factory():
        yield db_session

    monkeypatch.setattr(discovery_api, "SessionFactory", fake_session_factory)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        candidates = await client.get("/admin/candidates")
        stats = await client.get("/admin/discovery-stats")

    assert candidates.status_code == 200
    assert candidates.json()[0]["wallet_address"] == "candidate-sol-wallet"
    assert stats.status_code == 200
    assert stats.json()["candidate_wallets"] == 1
