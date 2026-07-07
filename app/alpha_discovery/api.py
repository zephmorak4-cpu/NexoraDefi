from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import desc, select

from app.alpha_discovery.audit import ALPHA_DISCOVERY_AUDIT
from app.alpha_discovery.jobs import scan_new_launches
from app.database.session import SessionFactory
from app.models import AlphaAlertHistory, AlphaScannedToken, AlphaWatchlistToken

router = APIRouter(prefix="/admin/alpha", tags=["alpha-discovery"])


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _scanned_token_payload(row: AlphaScannedToken) -> dict[str, Any]:
    return {
        "token": {
            "address": row.token_address,
            "pair_address": row.pair_address,
            "symbol": row.symbol,
            "name": row.name,
            "dex": row.dex,
            "source": row.source,
            "creator_wallet": row.creator_wallet,
        },
        "market": {
            "liquidity_usd": _value(row.liquidity_usd),
            "market_cap_usd": _value(row.market_cap_usd),
            "price_usd": _value(row.price_usd),
            "volume_usd": _value(row.volume_usd),
            "buys": row.buys,
            "sells": row.sells,
        },
        "assessment": {
            "final_score": _value(row.final_score),
            "decision": row.decision,
            "should_alert": row.should_alert,
            "reasons": row.rejection_reasons,
            "agent_scores": row.agent_scores,
        },
        "timestamps": {
            "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        },
    }


@router.post("/scan")
async def run_alpha_scan() -> dict[str, int]:
    return await scan_new_launches()


@router.get("/tokens")
async def list_alpha_tokens(limit: int = Query(25, ge=1, le=200)) -> list[dict[str, Any]]:
    async with SessionFactory() as session:
        rows = (
            await session.scalars(
                select(AlphaScannedToken).order_by(desc(AlphaScannedToken.last_seen_at)).limit(limit)
            )
        ).all()
    return [_scanned_token_payload(row) for row in rows]


@router.get("/watchlist")
async def list_alpha_watchlist(limit: int = Query(25, ge=1, le=200)) -> list[dict[str, Any]]:
    async with SessionFactory() as session:
        rows = (
            await session.scalars(
                select(AlphaWatchlistToken).order_by(desc(AlphaWatchlistToken.created_at)).limit(limit)
            )
        ).all()
    return [
        {
            "token_address": row.token_address,
            "decision": row.decision,
            "final_score": _value(row.final_score),
            "reasons": row.reasons,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/alerts")
async def list_alpha_alerts(limit: int = Query(25, ge=1, le=200)) -> list[dict[str, Any]]:
    async with SessionFactory() as session:
        rows = (
            await session.scalars(
                select(AlphaAlertHistory).order_by(desc(AlphaAlertHistory.created_at)).limit(limit)
            )
        ).all()
    return [
        {
            "token_address": row.token_address,
            "decision": row.decision,
            "final_score": _value(row.final_score),
            "channel": row.channel,
            "message": row.message,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/audit")
async def alpha_discovery_audit() -> dict[str, Any]:
    return ALPHA_DISCOVERY_AUDIT
