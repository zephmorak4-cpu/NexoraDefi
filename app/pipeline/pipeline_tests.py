from __future__ import annotations

from decimal import Decimal

from app.models import CandidateWallet
from app.pipeline.pipeline_state import PipelineStage, stage_at_least


class WalletPipelineQualityChecks:
    def scores_are_blocked_before_ranking(self, wallet: CandidateWallet) -> bool:
        if stage_at_least(wallet.pipeline_stage, PipelineStage.RANKED):
            return True
        return (
            Decimal(wallet.candidate_score or 0) == 0
            and Decimal(wallet.reputation_score or 0) == 0
            and Decimal(wallet.historical_accuracy_score or 0) == 0
        )

    def report_is_allowed(self, wallet: CandidateWallet) -> bool:
        return stage_at_least(wallet.pipeline_stage, PipelineStage.RANKED)
