from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zipfile import ZipFile

import httpx
from sqlalchemy import select

from app.intelligence.wallet_export import WalletReportExporter
from app.intelligence.wallet_message import build_wallet_report_completed_message
from app.intelligence.wallet_ranking import WalletRankingEngine
from app.intelligence.wallet_report import WalletReportEngine
from app.intelligence.wallet_review import WalletReviewService
from app.models import CandidateHistory, CandidateWallet, TrackedWallet, WalletReview
from app.core.config import Settings
from app.services.http import AsyncAPIClient
from app.telegram.client import TelegramClient


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
        pipeline_stage="RANKED",
        pipeline_status="READY",
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
    assert (tmp_path / "Wallet Intelligence Report.docx").exists()
    assert (tmp_path / "Wallet Intelligence Report.pdf").exists()
    with ZipFile(tmp_path / "Wallet Intelligence Report.docx") as archive:
        document_xml = archive.read("word/document.xml").decode()
    assert "candidate-review-wallet" in document_xml
    assert "Wallet Identity" in document_xml
    assert "Administrator Recommendation" in document_xml


def test_wallet_report_completed_message_is_human_readable():
    export = {
        "summary": {"total_wallets": 1},
        "docx_path": "/tmp/nexora-reports/Wallet Intelligence Report.docx",
        "pdf_path": "/tmp/nexora-reports/Wallet Intelligence Report.pdf",
        "rankings": [
            {
                "wallet_address": "Dmsjygi2eFZ2SvWZbmUduL7u24JD7BiNJ9eKvU1Ce4rB",
                "trading_style": "Market Maker",
                "copy_performance_score": "7.25",
                "wallet_reputation_score": "0",
                "historical_accuracy": "0",
                "risk_score": "70",
                "risk_classification": "Moderate Risk",
                "administrator_recommendation": "Needs More Observation",
                "recommendation_reasoning": "The wallet has too little observed history for a confident elite decision.",
            }
        ],
    }

    message = build_wallet_report_completed_message(export)

    assert "Candidate Wallet Address" in message
    assert "Copy Performance Score: estimated quality" in message
    assert "7.25/100" in message
    assert "Why The Scores Look Low" in message
    assert "manual approval" in message.lower()
    assert "Word Report" in message
    assert "every discovered wallet profile" in message


async def test_telegram_client_sends_word_document(tmp_path):
    docx_path = tmp_path / "Wallet Intelligence Report.docx"
    docx_path.write_bytes(b"PK\x03\x04")
    seen: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True, "result": {"document": {"file_name": docx_path.name}}})

    http_client = httpx.AsyncClient(base_url="https://api.telegram.org/bottest", transport=httpx.MockTransport(handler))
    client = TelegramClient("test", AsyncAPIClient("https://api.telegram.org/bottest", client=http_client))

    payload = await client.send_document(123, docx_path, caption="Word report ready")

    assert payload["ok"] is True
    assert seen["path"].endswith("/sendDocument")
    assert b"Wallet Intelligence Report.docx" in seen["body"]
    assert b"application/vnd.openxmlformats-officedocument.wordprocessingml.document" in seen["body"]
    await client.close()


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

