from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.models import MomentumMetric, SmartMoneySignal, Token, TokenGrowthMetric, TokenRiskMetric
from app.schemas.records import (
    MomentumMetricResponse,
    SmartMoneyWatchlistResponse,
    TokenGrowthMetricResponse,
)

router = APIRouter(prefix="/tokens", tags=["token-intelligence"])


def latest_ids(model, token_column):
    return select(func.max(model.id)).group_by(token_column)


@router.get("/trending", response_model=list[MomentumMetricResponse])
async def trending(
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[MomentumMetric]:
    return list(
        (
            await session.scalars(
                select(MomentumMetric)
                .where(MomentumMetric.id.in_(latest_ids(MomentumMetric, MomentumMetric.token_id)))
                .order_by(MomentumMetric.momentum_score.desc(), MomentumMetric.id.desc())
                .limit(limit)
            )
        ).all()
    )


@router.get("/watchlist", response_model=list[SmartMoneyWatchlistResponse])
async def watchlist(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    latest_signal_ids = select(func.max(SmartMoneySignal.id)).group_by(SmartMoneySignal.token_id)
    signals = list(
        (
            await session.scalars(
                select(SmartMoneySignal)
                .where(SmartMoneySignal.id.in_(latest_signal_ids))
                .order_by(SmartMoneySignal.signal_strength.desc(), SmartMoneySignal.id.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
    )
    token_ids = {signal.token_id for signal in signals}
    risks = await latest_risks(token_ids, session)
    growth = await latest_growth(token_ids, session)
    momentum = await latest_momentum(token_ids, session)
    tokens = {token.id: token for token in (await session.scalars(select(Token).where(Token.id.in_(token_ids)))).all()}
    return [
        {
            "token_id": signal.token_id,
            "symbol": tokens.get(signal.token_id).symbol if tokens.get(signal.token_id) else None,
            "signal_type": signal.signal_type,
            "signal_strength": signal.signal_strength,
            "confidence_score": signal.confidence_score,
            "number_of_smart_wallets": signal.number_of_smart_wallets,
            "total_capital_moved": signal.total_capital_moved,
            "risk_level": risks.get(signal.token_id).risk_level if risks.get(signal.token_id) else None,
            "overall_risk_score": risks.get(signal.token_id).overall_risk_score if risks.get(signal.token_id) else None,
            "liquidity_value": growth.get(signal.token_id).liquidity_value if growth.get(signal.token_id) else None,
            "momentum_stage": momentum.get(signal.token_id).momentum_stage if momentum.get(signal.token_id) else None,
            "created_at": signal.created_at,
        }
        for signal in signals
    ]


async def latest_risks(token_ids: set[int], session: AsyncSession) -> dict[int, TokenRiskMetric]:
    if not token_ids:
        return {}
    latest = select(func.max(TokenRiskMetric.id)).where(TokenRiskMetric.token_id.in_(token_ids)).group_by(TokenRiskMetric.token_id)
    return {
        risk.token_id: risk
        for risk in (
            await session.scalars(select(TokenRiskMetric).where(TokenRiskMetric.id.in_(latest)))
        ).all()
    }


async def latest_growth(token_ids: set[int], session: AsyncSession) -> dict[int, TokenGrowthMetric]:
    if not token_ids:
        return {}
    latest = select(func.max(TokenGrowthMetric.id)).where(TokenGrowthMetric.token_id.in_(token_ids)).group_by(TokenGrowthMetric.token_id)
    return {
        metric.token_id: metric
        for metric in (
            await session.scalars(select(TokenGrowthMetric).where(TokenGrowthMetric.id.in_(latest)))
        ).all()
    }


async def latest_momentum(token_ids: set[int], session: AsyncSession) -> dict[int, MomentumMetric]:
    if not token_ids:
        return {}
    latest = select(func.max(MomentumMetric.id)).where(MomentumMetric.token_id.in_(token_ids)).group_by(MomentumMetric.token_id)
    return {
        metric.token_id: metric
        for metric in (
            await session.scalars(select(MomentumMetric).where(MomentumMetric.id.in_(latest)))
        ).all()
    }


@router.get("/{token_id}/growth", response_model=TokenGrowthMetricResponse)
async def token_growth(
    token_id: int, session: AsyncSession = Depends(get_session)
) -> TokenGrowthMetric:
    if await session.get(Token, token_id) is None:
        raise HTTPException(status_code=404, detail="token not found")
    metric = await session.scalar(
        select(TokenGrowthMetric)
        .where(TokenGrowthMetric.token_id == token_id)
        .order_by(TokenGrowthMetric.id.desc())
        .limit(1)
    )
    if not metric:
        raise HTTPException(status_code=404, detail="growth metrics not calculated")
    return metric


@router.get("/{token_id}/momentum", response_model=MomentumMetricResponse)
async def token_momentum(
    token_id: int, session: AsyncSession = Depends(get_session)
) -> MomentumMetric:
    if await session.get(Token, token_id) is None:
        raise HTTPException(status_code=404, detail="token not found")
    metric = await session.scalar(
        select(MomentumMetric)
        .where(MomentumMetric.token_id == token_id)
        .order_by(MomentumMetric.id.desc())
        .limit(1)
    )
    if not metric:
        raise HTTPException(status_code=404, detail="momentum metrics not calculated")
    return metric
