from __future__ import annotations

from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.wallet_classifier import WalletClassifier
from app.models import CandidateHistory, CandidatePortfolioSnapshot, CandidateTokenHistory, CandidateWallet
from app.pipeline.wallet_ingestion import StoredWalletEvidenceProvider, WalletEvidenceProvider
from app.pipeline.pipeline_state import PipelineStage, PipelineStatus, normalize_stage
from app.pipeline.pipeline_validator import WalletPipelineValidator


class WalletScorer(Protocol):
    async def score_wallet(self, wallet: CandidateWallet):
        ...

    async def reputation_score(self, wallet: CandidateWallet):
        ...

    async def historical_accuracy(self, wallet: CandidateWallet):
        ...


class WalletPipelineManager:
    def __init__(
        self,
        session: AsyncSession,
        scorer: WalletScorer,
        validator: WalletPipelineValidator | None = None,
        classifier: WalletClassifier | None = None,
        evidence_provider: WalletEvidenceProvider | None = None,
    ) -> None:
        self.session = session
        self.scorer = scorer
        self.validator = validator or WalletPipelineValidator()
        self.classifier = classifier or WalletClassifier()
        self.evidence_provider = evidence_provider or StoredWalletEvidenceProvider(session)

    async def run_all(self) -> int:
        wallets = list(
            (
                await self.session.scalars(
                    select(CandidateWallet).where(CandidateWallet.status == "observing")
                )
            ).all()
        )
        advanced = 0
        for wallet in wallets:
            advanced += int(await self.advance_wallet(wallet))
        await self.session.commit()
        return advanced

    async def advance_wallet(self, wallet: CandidateWallet) -> bool:
        history = await self._history(wallet.id)
        original_stage = normalize_stage(wallet.pipeline_stage)
        wallet.pipeline_status = PipelineStatus.IN_PROGRESS.value
        wallet.pipeline_error = None

        await self.evidence_provider.download_transactions(wallet)
        history = await self._history(wallet.id)
        if not self.validator.has_complete_transactions(history):
            self._stop(wallet, PipelineStatus.INSUFFICIENT_HISTORY, "Insufficient historical data")
            return False
        self._advance(wallet, PipelineStage.TRANSACTIONS_DOWNLOADED)

        await self.evidence_provider.download_portfolio(wallet)
        snapshot = await self._latest_portfolio(wallet.id)
        if not self.validator.has_portfolio_evidence(snapshot):
            self._stop(wallet, PipelineStatus.INSUFFICIENT_PORTFOLIO_DATA, "Insufficient portfolio data")
            return False
        self._advance(wallet, PipelineStage.PORTFOLIO_DOWNLOADED)

        await self.evidence_provider.download_token_history(wallet)
        token_history = await self._token_history(wallet.id)
        if not self.validator.has_token_history(history, token_history):
            self._stop(wallet, PipelineStatus.INSUFFICIENT_TOKEN_HISTORY, "Insufficient token history")
            return False
        self._advance(wallet, PipelineStage.TOKEN_HISTORY_DOWNLOADED)

        wallet.wallet_type = self.classifier.classify(history)
        self._advance(wallet, PipelineStage.PROFILE_BUILT)

        if not self.validator.has_completed_backtest_data(history, token_history):
            self._stop(wallet, PipelineStatus.INSUFFICIENT_BACKTEST_DATA, "Insufficient completed trades for backtesting")
            return False
        self._advance(wallet, PipelineStage.BACKTEST_COMPLETED)

        wallet.candidate_score = await self.scorer.score_wallet(wallet)
        self._advance(wallet, PipelineStage.COPY_SCORE_COMPLETED)

        wallet.reputation_score = await self.scorer.reputation_score(wallet)
        wallet.historical_accuracy_score = await self.scorer.historical_accuracy(wallet)
        self._advance(wallet, PipelineStage.REPUTATION_COMPLETED)

        self._advance(wallet, PipelineStage.CONVICTION_COMPLETED)
        self._advance(wallet, PipelineStage.RANKED)
        wallet.pipeline_status = PipelineStatus.READY.value
        return normalize_stage(wallet.pipeline_stage) != original_stage

    def mark_report_generated(self, wallet: CandidateWallet) -> None:
        self._advance(wallet, PipelineStage.REPORT_GENERATED)
        wallet.pipeline_status = PipelineStatus.READY.value

    @staticmethod
    def _advance(wallet: CandidateWallet, stage: PipelineStage) -> None:
        wallet.pipeline_stage = stage.value

    @staticmethod
    def _stop(wallet: CandidateWallet, status: PipelineStatus, error: str) -> None:
        wallet.pipeline_status = status.value
        wallet.pipeline_error = error

    async def _history(self, wallet_id: int) -> list[CandidateHistory]:
        return list(
            (
                await self.session.scalars(
                    select(CandidateHistory)
                    .where(CandidateHistory.wallet_id == wallet_id)
                    .order_by(CandidateHistory.timestamp, CandidateHistory.id)
                )
            ).all()
        )

    async def _latest_portfolio(self, wallet_id: int) -> CandidatePortfolioSnapshot | None:
        return await self.session.scalar(
            select(CandidatePortfolioSnapshot)
            .where(CandidatePortfolioSnapshot.wallet_id == wallet_id)
            .order_by(CandidatePortfolioSnapshot.created_at.desc(), CandidatePortfolioSnapshot.id.desc())
        )

    async def _token_history(self, wallet_id: int) -> list[CandidateTokenHistory]:
        return list(
            (
                await self.session.scalars(
                    select(CandidateTokenHistory).where(CandidateTokenHistory.wallet_id == wallet_id)
                )
            ).all()
        )
