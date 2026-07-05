from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select

from app.intelligence import intelligence_api
from app.intelligence.wallet_export import WalletReportExporter
from app.intelligence.wallet_ranking import WalletRankingEngine
from app.intelligence.wallet_report import WalletReportEngine
from app.intelligence.wallet_review import WalletReviewService
from app.main import app
from app.models import CandidateHistory, CandidateWallet, TrackedWallet, WalletReview
from app.core.config import Settings


async def seed_candidate(db_session, score: Decimal = Decimal("90")) -> CandidateWallet:
    candidate = CandidateWallet(
        wallet_address="candidate-review-wallet",
        chain="solana",
        first_seen=datetime.now(timezone.utc) - timedelta(days=10),
        last_seen=datetime.now(timezone.utc),
        discovery_reason="large_trending_token_interaction",
        wallet_type="Market Maker",
        candidate_score=score,
        reputation_score=Decimal("88"),
        historical_accuracy_score=Decimal("82"),
        suspicious_score=Decimal("0"),
        status="observing",
    )
    db_session.add(candidate)
    await db_session.flush()
    db_session.add_all(
        [
            CandidateHistory(
                wallet_id=candidate.id,
                token="TokenA",
                action="swap",
                amount=Decimal("10"),
                usd_value=Decimal("10000"),
                timestamp=datetime.now(timezone.utc) - timedelta(days=2),
            ),
            CandidateHistory(
                wallet_id=candidate.id,
                token="TokenA",
                action="swap",
                amount=Decimal("12"),
                usd_value=Decimal("15000"),
                timestamp=datetime.now(timezone.utc) - timedelta(days=1),
            ),
            CandidateHistory(
                wallet_id=candidate.id,
                token="TokenB",
                action="buy",
                amount=Decimal("3"),
                usd_value=Decimal("5000"),
                timestamp=datetime.now(timezone.utc),
            ),
        ]
    )
    await db_session.commit()
    return candidate


async def test_wallet_report_ranking_and_export(db_session, tmp_path):
    candidate = await seed_candidate(db_session)

    report = await WalletReportEngine(db_session).report_for_wallet(candidate.id)
    rankings = WalletRankingEngine().rank([report])
    export = WalletReportExporter().export([report], tmp_path)

    assert report.wallet_address == "candidate-review-wallet"
    assert report.administrator_recommendation in {
        "Strong Elite Candidate",
        "Promising Candidate",
        "Needs More Observation",
        "Reject",
    }
    assert rankings[0].wallet_id == candidate.id
    assert export["summary"]["total_wallets"] == 1
    assert (tmp_path / "Wallet Intelligence Report.pdf").exists()


async def test_manual_approval_creates_review_and_tracked_wallet(db_session):
    candidate = await seed_candidate(db_session)

    review = await WalletReviewService(db_session, Settings()).approve(
        candidate.id,
        reviewed_by="admin",
        notes="manual approval",
    )

    tracked = await db_session.scalar(select(TrackedWallet))
    assert review.review_status == "Approved"
    assert review.approved_for_signals is True
    assert tracked.wallet_address == candidate.wallet_address
    assert tracked.status == "active"


async def test_reject_and_needs_observation_do_not_track_wallet(db_session):
    rejected = await seed_candidate(db_session, score=Decimal("20"))
    service = WalletReviewService(db_session, Settings())

    reject_review = await service.reject(rejected.id, reviewed_by="admin", notes="too risky")
    observation_review = await service.needs_observation(rejected.id, reviewed_by="admin", notes="watch longer")

    assert reject_review.review_status in {"Rejected", "Needs Observation"}
    assert observation_review.review_status == "Needs Observation"
    assert await db_session.scalar(select(TrackedWallet)) is None


async def test_intelligence_admin_api_reports_and_approval(db_session, monkeypatch):
    candidate = await seed_candidate(db_session)

    @asynccontextmanager
    async def fake_session_factory():
        yield db_session

    monkeypatch.setattr(intelligence_api, "SessionFactory", fake_session_factory)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        reports = await client.get("/admin/reports?send_telegram=false")
        rankings = await client.get("/admin/rankings")
        wallet = await client.get(f"/admin/wallet/{candidate.id}")
        approved = await client.post("/admin/approve-wallet", json={"wallet_id": candidate.id, "reviewed_by": "admin"})

    assert reports.status_code == 200
    assert reports.json()["summary"]["total_wallets"] == 1
    assert rankings.status_code == 200
    assert rankings.json()[0]["wallet_address"] == candidate.wallet_address
    assert wallet.status_code == 200
    assert approved.status_code == 200
    assert (await db_session.scalar(select(WalletReview))).approved_for_signals is True
