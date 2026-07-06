from datetime import datetime, timezone
from decimal import Decimal

from app.core.config import Settings
from app.discovery.candidate_scoring import CandidateScoringEngine
from app.models import CandidateHistory, CandidateWallet
from app.pipeline.pipeline_state import PipelineStatus
from app.pipeline.wallet_pipeline import WalletPipelineManager


class FailingEvidenceProvider:
    async def download_transactions(self, wallet):
        raise RuntimeError("provider unavailable")

    async def download_portfolio(self, wallet):
        return False

    async def download_token_history(self, wallet):
        return 0

    async def close(self):
        return None


async def test_pipeline_marks_failed_stage_without_crashing_job(db_session):
    wallet = CandidateWallet(wallet_address="failing-wallet", chain="solana", discovery_reason="test", status="observing")
    db_session.add(wallet)
    await db_session.flush()
    db_session.add(
        CandidateHistory(
            wallet_id=wallet.id,
            token="TokenA",
            action="buy",
            amount=Decimal("1"),
            usd_value=Decimal("100"),
            timestamp=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    processed = await WalletPipelineManager(
        db_session,
        CandidateScoringEngine(db_session, settings=Settings()),
        evidence_provider=FailingEvidenceProvider(),
    ).run_all()

    refreshed = await db_session.get(CandidateWallet, wallet.id)
    assert processed == 0
    assert refreshed.pipeline_status == PipelineStatus.FAILED.value
    assert "download_transactions failed" in refreshed.pipeline_error
