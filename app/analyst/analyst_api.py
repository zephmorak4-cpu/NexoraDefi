from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.analyst_engine import AnalystEngine
from app.core.config import get_settings
from app.database.session import get_session
from app.schemas.records import AnalystReportResponse

router = APIRouter(prefix="/analyst", tags=["crypto-analyst"])


@router.get("/token/{token_id}", response_model=AnalystReportResponse)
async def analyst_token(
    token_id: int,
    format: str = Query("markdown", pattern="^(markdown|plain|telegram)$"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    report = await AnalystEngine(session, get_settings()).token_report(token_id, output_format=format)
    return report_payload(report)


@router.get("/watchlist", response_model=list[AnalystReportResponse])
async def analyst_watchlist(
    limit: int = Query(20, ge=1, le=100),
    format: str = Query("markdown", pattern="^(markdown|plain|telegram)$"),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    reports = await AnalystEngine(session, get_settings()).watchlist_reports(limit=limit, output_format=format)
    return [report_payload(report) for report in reports]


@router.get("/smart-money", response_model=AnalystReportResponse)
async def analyst_smart_money(
    limit: int = Query(20, ge=1, le=100),
    format: str = Query("markdown", pattern="^(markdown|plain|telegram)$"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    report = await AnalystEngine(session, get_settings()).smart_money_report(output_format=format, limit=limit)
    return report_payload(report)


def report_payload(report) -> dict:
    return {
        "report_type": report.report_type,
        "format": report.format,
        "language": report.language,
        "content": report.content,
        "evidence": report.evidence,
    }
