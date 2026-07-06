from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, func, select

from app.core.config import get_settings
from app.database.session import SessionFactory
from app.discovery.discovery_jobs import discover_candidate_wallets, update_candidate_scores
from app.discovery.wallet_history import WalletHistoryService
from app.discovery.wallet_promotion import WalletPromotionService
from app.intelligence.wallet_review import WalletReviewService
from app.models import CandidateHistory, CandidateWallet, TrackedWallet

router = APIRouter(prefix="/admin", tags=["wallet-discovery"])


class CandidateHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    signature: str | None = None
    token: str
    action: str
    direction: str | None = None
    amount: Decimal
    usd_value: Decimal | None
    dex: str | None = None
    fees: Decimal | None = None
    counterparty: str | None = None
    timestamp: datetime


class CandidateWalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_address: str
    chain: str
    first_seen: datetime
    last_seen: datetime
    discovery_reason: str
    wallet_type: str
    candidate_score: Decimal
    reputation_score: Decimal
    historical_accuracy_score: Decimal
    suspicious_score: Decimal
    status: str
    pipeline_stage: str
    pipeline_status: str
    pipeline_error: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class CandidateDetailResponse(CandidateWalletResponse):
    history: list[CandidateHistoryResponse] = Field(default_factory=list)


class CandidateActionRequest(BaseModel):
    candidate_id: int
    notes: str | None = None


@router.get("/candidates", response_model=list[CandidateWalletResponse])
async def candidates(status: str | None = None) -> list[CandidateWallet]:
    async with SessionFactory() as session:
        query = select(CandidateWallet).order_by(desc(CandidateWallet.candidate_score), desc(CandidateWallet.last_seen))
        if status:
            query = query.where(CandidateWallet.status == status)
        return list((await session.scalars(query)).all())


@router.post("/run-discovery")
async def run_discovery() -> dict[str, int]:
    discovered = await discover_candidate_wallets()
    return {"discovered": discovered}


@router.post("/run-wallet-pipeline")
async def run_wallet_pipeline() -> dict[str, int]:
    processed = await update_candidate_scores()
    return {"processed": processed}


@router.get("/candidate/{candidate_id}", response_model=CandidateDetailResponse)
async def candidate(candidate_id: int) -> CandidateDetailResponse:
    async with SessionFactory() as session:
        wallet = await session.get(CandidateWallet, candidate_id)
        if wallet is None:
            raise HTTPException(status_code=404, detail="candidate wallet not found")
        history = await WalletHistoryService(session).for_candidate(candidate_id)
        return CandidateDetailResponse.model_validate(wallet).model_copy(update={"history": history})


@router.post("/promote")
async def promote(payload: CandidateActionRequest) -> dict[str, bool]:
    async with SessionFactory() as session:
        wallet = await session.get(CandidateWallet, payload.candidate_id)
        if wallet is None:
            raise HTTPException(status_code=404, detail="candidate wallet not found")
        await WalletReviewService(session, get_settings()).approve(wallet.id, reviewed_by="admin", notes=payload.notes)
        return {"promoted": True}


@router.post("/reject")
async def reject(payload: CandidateActionRequest) -> dict[str, bool]:
    async with SessionFactory() as session:
        wallet = await session.get(CandidateWallet, payload.candidate_id)
        if wallet is None:
            raise HTTPException(status_code=404, detail="candidate wallet not found")
        await WalletPromotionService(session, get_settings()).reject(wallet, payload.notes)
        return {"rejected": True}


@router.get("/elite-wallets")
async def elite_wallets() -> list[dict[str, object]]:
    async with SessionFactory() as session:
        wallets = list(
            (
                await session.scalars(
                    select(TrackedWallet)
                    .where(TrackedWallet.status == "active")
                    .order_by(desc(TrackedWallet.reputation_score), TrackedWallet.id)
                )
            ).all()
        )
        return [
            {
                "id": wallet.id,
                "wallet_address": wallet.wallet_address,
                "chain": wallet.chain,
                "wallet_label": wallet.wallet_label,
                "wallet_category": wallet.wallet_category,
                "source": wallet.source,
                "reputation_score": wallet.reputation_score,
                "status": wallet.status,
            }
            for wallet in wallets
        ]


@router.get("/discovery-stats")
async def discovery_stats() -> dict[str, object]:
    async with SessionFactory() as session:
        candidate_count = await session.scalar(select(func.count(CandidateWallet.id)))
        elite_count = await session.scalar(select(func.count(TrackedWallet.id)).where(TrackedWallet.status == "active"))
        promotions = await session.scalar(select(func.count(CandidateWallet.id)).where(CandidateWallet.status == "promoted"))
        demotions = await session.scalar(select(func.count(TrackedWallet.id)).where(TrackedWallet.status == "observing"))
        average_candidate_score = await session.scalar(select(func.avg(CandidateWallet.candidate_score)))
        average_reputation = await session.scalar(select(func.avg(CandidateWallet.reputation_score)))
        classifications = (
            await session.execute(
                select(CandidateWallet.wallet_type, func.count(CandidateWallet.id)).group_by(CandidateWallet.wallet_type)
            )
        ).all()
        return {
            "candidate_wallets": candidate_count or 0,
            "elite_wallets": elite_count or 0,
            "promotions": promotions or 0,
            "demotions": demotions or 0,
            "average_candidate_score": average_candidate_score or 0,
            "average_wallet_reputation": average_reputation or 0,
            "wallet_classifications": {wallet_type: count for wallet_type, count in classifications},
        }
