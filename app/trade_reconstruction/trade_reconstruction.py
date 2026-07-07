from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateHistory, CandidateWallet, WalletPosition
from app.core.config import get_settings
from app.market_context.market_context import MarketContextEngine
from app.trade_reconstruction.position_builder import PositionBuilder
from app.trade_reconstruction.position_matcher import PositionMatcher
from app.trade_reconstruction.position_summary import PositionSummary


class TradeReconstructionEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.matcher = PositionMatcher()
        self.builder = PositionBuilder()
        self.summaries = PositionSummary()

    async def rebuild_all(self) -> int:
        wallets = list((await self.session.scalars(select(CandidateWallet).where(CandidateWallet.status == "observing"))).all())
        rebuilt = 0
        for wallet in wallets:
            rebuilt += await self.rebuild_wallet(wallet.id)
        await self.session.commit()
        return rebuilt

    async def rebuild_wallet(self, wallet_id: int) -> int:
        history = list(
            (
                await self.session.scalars(
                    select(CandidateHistory).where(CandidateHistory.wallet_id == wallet_id).order_by(CandidateHistory.timestamp)
                )
            ).all()
        )
        await self.session.execute(delete(WalletPosition).where(WalletPosition.candidate_wallet_id == wallet_id))
        built = 0
        for (_, token), rows in self.matcher.group(history).items():
            position = self.builder.build(wallet_id, token, rows)
            if position is not None:
                self.session.add(position)
                built += 1
        await self.session.flush()
        await MarketContextEngine(self.session, get_settings()).enrich_wallet_positions(wallet_id)
        return built

    async def positions(self, wallet_address: str | None = None) -> list[WalletPosition]:
        query = select(WalletPosition).where(WalletPosition.candidate_wallet_id.is_not(None))
        if wallet_address:
            query = query.join(CandidateWallet, CandidateWallet.id == WalletPosition.candidate_wallet_id).where(
                CandidateWallet.wallet_address == wallet_address
            )
        return list((await self.session.scalars(query.order_by(WalletPosition.entry_time.desc(), WalletPosition.id.desc()))).all())

    async def summary(self) -> dict[str, object]:
        return self.summaries.build(await self.positions())
