from datetime import datetime, timezone
from decimal import Decimal

from app.core.config import Settings
from sqlalchemy import select

from app.models import CandidateHistory, CandidateWallet
from app.trade_reconstruction.cost_basis import CostBasisEnrichmentEngine
from app.trade_reconstruction.trade_reconstruction import TradeReconstructionEngine


class FixedPriceProvider:
    async def price(self, token: str) -> Decimal | None:
        return Decimal("2") if token == "TokenA" else None

    async def close(self) -> None:
        return None


async def test_cost_basis_enrichment_prices_missing_candidate_history(db_session):
    wallet = CandidateWallet(wallet_address="cost-wallet", chain="solana", discovery_reason="test", status="observing")
    db_session.add(wallet)
    await db_session.flush()
    db_session.add(
        CandidateHistory(
            wallet_id=wallet.id,
            signature="buy",
            token="TokenA",
            action="buy",
            amount=Decimal("10"),
            usd_value=None,
            timestamp=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    enriched = await CostBasisEnrichmentEngine(db_session, Settings(), FixedPriceProvider()).enrich_missing_history()

    row = await db_session.scalar(select(CandidateHistory).where(CandidateHistory.wallet_id == wallet.id))
    assert enriched == 1
    assert row.usd_value == Decimal("20.00")


async def test_rebuild_positions_uses_enriched_cost_basis(db_session):
    wallet = CandidateWallet(wallet_address="cost-position-wallet", chain="solana", discovery_reason="test", status="observing")
    db_session.add(wallet)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            CandidateHistory(wallet_id=wallet.id, signature="buy", token="TokenA", action="buy", amount=Decimal("10"), usd_value=None, timestamp=now),
            CandidateHistory(wallet_id=wallet.id, signature="sell", token="TokenA", action="sell", amount=Decimal("10"), usd_value=None, timestamp=now),
        ]
    )
    await db_session.commit()

    await CostBasisEnrichmentEngine(db_session, Settings(), FixedPriceProvider()).enrich_missing_history()
    rebuilt = await TradeReconstructionEngine(db_session).rebuild_wallet(wallet.id)

    assert rebuilt == 1
