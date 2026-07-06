from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.config import Settings
from app.discovery.candidate_scoring import CandidateScoringEngine
from app.intelligence.wallet_report import WalletReportEngine
from app.models import CandidateHistory, CandidateWallet
from app.pipeline.pipeline_state import PipelineStage, PipelineStatus


async def _candidate(db_session, events: list[CandidateHistory] | None = None) -> CandidateWallet:
    wallet = CandidateWallet(
        wallet_address="pipeline-wallet",
        chain="solana",
        discovery_reason="test",
        status="observing",
        pipeline_stage=PipelineStage.DISCOVERED.value,
        pipeline_status=PipelineStatus.PENDING.value,
    )
    db_session.add(wallet)
    await db_session.flush()
    for event in events or []:
        event.wallet_id = wallet.id
        db_session.add(event)
    await db_session.commit()
    return wallet


def _history(action: str, token: str, days_ago: int, value: str) -> CandidateHistory:
    return CandidateHistory(
        wallet_id=0,
        token=token,
        action=action,
        amount=Decimal("10"),
        usd_value=Decimal(value),
        timestamp=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )


async def test_pipeline_stops_before_scoring_when_history_is_insufficient(db_session):
    wallet = await _candidate(db_session, [_history("swap", "TokenA", 1, "1000")])

    processed = await CandidateScoringEngine(db_session, Settings()).score_all()

    refreshed = await db_session.get(CandidateWallet, wallet.id)
    assert processed == 0
    assert refreshed.pipeline_stage == PipelineStage.DISCOVERED.value
    assert refreshed.pipeline_status == PipelineStatus.INSUFFICIENT_HISTORY.value
    assert refreshed.candidate_score == 0
    assert refreshed.reputation_score == 0
    assert refreshed.historical_accuracy_score == 0
    with pytest.raises(ValueError, match="insufficient historical data"):
        await WalletReportEngine(db_session).report_for_wallet(wallet.id)


async def test_pipeline_scores_only_after_ordered_evidence_stages_complete(db_session):
    wallet = await _candidate(
        db_session,
        [
            _history("buy", "TokenA", 8, "1000"),
            _history("buy", "TokenA", 7, "1100"),
            _history("sell", "TokenA", 6, "1500"),
            _history("swap", "TokenB", 5, "2000"),
            _history("sell", "TokenB", 4, "1800"),
        ],
    )

    processed = await CandidateScoringEngine(db_session, Settings()).score_all()

    refreshed = await db_session.get(CandidateWallet, wallet.id)
    assert processed == 1
    assert refreshed.pipeline_stage == PipelineStage.RANKED.value
    assert refreshed.pipeline_status == PipelineStatus.READY.value
    assert refreshed.candidate_score > 0
    assert refreshed.reputation_score > 0
    assert refreshed.historical_accuracy_score > 0
    report = await WalletReportEngine(db_session).report_for_wallet(wallet.id)
    assert report.wallet_address == "pipeline-wallet"
