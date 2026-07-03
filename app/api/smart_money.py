from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.models import SmartMoneySignal, Token, Wallet, WalletMetric, WalletPosition, WalletScore
from app.schemas.records import (
    RankedWalletResponse,
    SmartMoneySignalResponse,
    WalletMetricResponse,
    WalletPositionResponse,
    WalletProfileResponse,
    WalletScoreResponse,
)

router = APIRouter(prefix="/smart-money", tags=["smart-money"])


def latest_score_ids():
    return select(func.max(WalletScore.id)).group_by(WalletScore.wallet_id)


def ranked_wallet(score: WalletScore, wallet: Wallet) -> RankedWalletResponse:
    return RankedWalletResponse(
        wallet_address=wallet.wallet_address,
        chain=wallet.chain,
        score=WalletScoreResponse.model_validate(score),
    )


@router.get("/wallets", response_model=list[RankedWalletResponse])
async def wallets(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[RankedWalletResponse]:
    rows = (
        await session.execute(
            select(WalletScore, Wallet)
            .join(Wallet, Wallet.id == WalletScore.wallet_id)
            .where(WalletScore.id.in_(latest_score_ids()))
            .order_by(WalletScore.final_smart_money_score.desc(), WalletScore.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return [ranked_wallet(score, wallet) for score, wallet in rows]


@router.get("/wallets/{address}", response_model=WalletProfileResponse)
async def wallet_profile(
    address: str, session: AsyncSession = Depends(get_session)
) -> WalletProfileResponse:
    wallet = await session.scalar(
        select(Wallet).where(func.lower(Wallet.wallet_address) == address.lower())
    )
    if not wallet:
        raise HTTPException(status_code=404, detail="wallet not found")
    score = await session.scalar(
        select(WalletScore)
        .where(WalletScore.wallet_id == wallet.id)
        .order_by(WalletScore.id.desc())
        .limit(1)
    )
    if not score:
        raise HTTPException(status_code=404, detail="wallet has not been scored")
    metric = await session.scalar(
        select(WalletMetric).where(WalletMetric.wallet_id == wallet.id)
    )
    positions = (
        await session.scalars(
            select(WalletPosition)
            .where(WalletPosition.wallet_id == wallet.id)
            .order_by(WalletPosition.latest_activity_date.desc())
            .limit(500)
        )
    ).all()
    return WalletProfileResponse(
        wallet_address=wallet.wallet_address,
        chain=wallet.chain,
        score=WalletScoreResponse.model_validate(score),
        metrics=WalletMetricResponse.model_validate(metric) if metric else None,
        positions=[WalletPositionResponse.model_validate(position) for position in positions],
    )


@router.get("/signals", response_model=list[SmartMoneySignalResponse])
async def signals(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[SmartMoneySignal]:
    return list(
        (
            await session.scalars(
                select(SmartMoneySignal)
                .order_by(SmartMoneySignal.created_at.desc(), SmartMoneySignal.id.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
    )


@router.get("/top-wallets", response_model=list[RankedWalletResponse])
async def top_wallets(
    limit: int = Query(25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RankedWalletResponse]:
    return await wallets(limit=limit, offset=0, session=session)


@router.get("/tokens/{token_id}")
async def token_activity(
    token_id: int,
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    if await session.get(Token, token_id) is None:
        raise HTTPException(status_code=404, detail="token not found")
    positions = (
        await session.scalars(
            select(WalletPosition)
            .where(WalletPosition.token_id == token_id)
            .order_by(WalletPosition.latest_activity_date.desc())
            .limit(limit)
        )
    ).all()
    token_signals = (
        await session.scalars(
            select(SmartMoneySignal)
            .where(SmartMoneySignal.token_id == token_id)
            .order_by(SmartMoneySignal.created_at.desc())
            .limit(limit)
        )
    ).all()
    return {
        "token_id": token_id,
        "positions": [WalletPositionResponse.model_validate(position) for position in positions],
        "signals": [SmartMoneySignalResponse.model_validate(signal) for signal in token_signals],
    }
