from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.session import get_session
from app.models import RiskEvent, Token, TokenRiskMetric
from app.schemas.records import RiskEventResponse, TokenRiskAnalysisResponse, TokenRiskMetricResponse
from app.services.risk import RiskAnalyzer

router = APIRouter(prefix="/risk", tags=["risk-intelligence"])


def latest_risk_ids():
    return select(func.max(TokenRiskMetric.id)).group_by(TokenRiskMetric.token_id)


@router.get("/tokens/{token_id}", response_model=TokenRiskAnalysisResponse)
async def token_risk(token_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    if await session.get(Token, token_id) is None:
        raise HTTPException(status_code=404, detail="token not found")
    metric = await session.scalar(
        select(TokenRiskMetric)
        .where(TokenRiskMetric.token_id == token_id)
        .order_by(TokenRiskMetric.id.desc())
        .limit(1)
    )
    if not metric:
        raise HTTPException(status_code=404, detail="risk metrics not calculated")
    analyzer = RiskAnalyzer(session, get_settings())
    holder_score, holder_data = await analyzer.holder_distribution(token_id)
    liquidity_score, liquidity_data = await analyzer.liquidity(token_id)
    volatility_score, volatility_data = await analyzer.volatility(token_id, metric.calculated_at)
    age_score, age_data = await analyzer.age(token_id, metric.calculated_at)
    smart_money_score, smart_money_data = await analyzer.smart_money_exit(token_id, metric.calculated_at)
    contract_score, contract_data = await analyzer.contract_security(token_id)
    return {
        "id": metric.id,
        "token_id": metric.token_id,
        "holder_concentration_score": metric.holder_concentration_score,
        "liquidity_risk_score": metric.liquidity_risk_score,
        "volatility_risk_score": metric.volatility_risk_score,
        "age_risk_score": metric.age_risk_score,
        "smart_money_exit_risk_score": metric.smart_money_exit_risk_score,
        "contract_security_score": metric.contract_security_score,
        "overall_risk_score": metric.overall_risk_score,
        "risk_level": metric.risk_level,
        "calculated_at": metric.calculated_at,
        "risk_factors": {
            "holder_distribution": {"score": holder_score, **holder_data},
            "liquidity": {"score": liquidity_score, **liquidity_data},
            "volatility": {"score": volatility_score, **volatility_data},
            "project_age": {"score": age_score, **age_data},
            "smart_money_behavior": {"score": smart_money_score, **smart_money_data},
            "contract_security": {"score": contract_score, **contract_data},
        },
    }


@router.get("/events", response_model=list[RiskEventResponse])
async def risk_events(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[RiskEvent]:
    return list(
        (
            await session.scalars(
                select(RiskEvent).order_by(RiskEvent.created_at.desc(), RiskEvent.id.desc()).offset(offset).limit(limit)
            )
        ).all()
    )


@router.get("/high-risk", response_model=list[TokenRiskMetricResponse])
async def high_risk(
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[TokenRiskMetric]:
    return list(
        (
            await session.scalars(
                select(TokenRiskMetric)
                .where(TokenRiskMetric.id.in_(latest_risk_ids()), TokenRiskMetric.risk_level == "HIGH")
                .order_by(TokenRiskMetric.overall_risk_score.asc(), TokenRiskMetric.id.desc())
                .limit(limit)
            )
        ).all()
    )


@router.get("/low-risk", response_model=list[TokenRiskMetricResponse])
async def low_risk(
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[TokenRiskMetric]:
    return list(
        (
            await session.scalars(
                select(TokenRiskMetric)
                .where(TokenRiskMetric.id.in_(latest_risk_ids()), TokenRiskMetric.risk_level == "LOW")
                .order_by(TokenRiskMetric.overall_risk_score.desc(), TokenRiskMetric.id.desc())
                .limit(limit)
            )
        ).all()
    )
