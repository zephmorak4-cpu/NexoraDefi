from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import desc, func, select

from app.alpha_discovery.audit import ALPHA_DISCOVERY_AUDIT
from app.alpha_discovery.jobs import scan_new_launches, send_alpha_discovery_report, send_alpha_watchlist_digest
from app.alpha_discovery.services import MarketDataService
from app.core.config import get_settings
from app.database.session import SessionFactory
from app.models import AlphaAlertHistory, AlphaProviderSnapshot, AlphaScannedToken, AlphaWatchlistToken

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


def _reason_summary(reason_rows: list[list[str] | None], limit: int = 12) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for reasons in reason_rows:
        for reason in reasons or []:
            counts[reason] = counts.get(reason, 0) + 1
    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


@router.post("/scan")
async def run_alpha_scan() -> dict[str, Any]:
    return await scan_new_launches()


@router.get("/provider-check")
async def alpha_provider_check() -> dict[str, Any]:
    settings = get_settings()
    market_data = MarketDataService(settings)
    try:
        launches = await market_data.latest_solana_launches()
        return {
            "launch_detector": market_data.last_launch_diagnostics,
            "provider_health": market_data.health.snapshot(),
            "sample": [
                {
                    "token_address": token.token_address,
                    "symbol": token.symbol,
                    "pair_address": token.pair_address,
                    "dex": token.dex,
                    "launch_time": token.launch_time,
                    "liquidity_usd": token.liquidity_usd,
                    "volume_usd": token.volume_usd,
                }
                for token in launches[:10]
            ],
        }
    finally:
        await market_data.close()


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


@router.get("/diagnostics")
async def alpha_diagnostics() -> dict[str, Any]:
    settings = get_settings()
    async with SessionFactory() as session:
        total_scanned = await session.scalar(select(func.count()).select_from(AlphaScannedToken))
        latest_seen = await session.scalar(select(func.max(AlphaScannedToken.last_seen_at)))
        decisions = (
            await session.execute(
                select(AlphaScannedToken.decision, func.count())
                .group_by(AlphaScannedToken.decision)
                .order_by(desc(func.count()))
            )
        ).all()
        watchlist_decisions = (
            await session.execute(
                select(AlphaWatchlistToken.decision, func.count())
                .group_by(AlphaWatchlistToken.decision)
                .order_by(desc(func.count()))
            )
        ).all()
        alerts_total = await session.scalar(select(func.count()).select_from(AlphaAlertHistory))
        provider_rows = (
            await session.execute(
                select(
                    AlphaProviderSnapshot.provider,
                    func.count(),
                    func.max(AlphaProviderSnapshot.created_at),
                )
                .group_by(AlphaProviderSnapshot.provider)
                .order_by(desc(func.count()))
            )
        ).all()
        reason_rows = (await session.scalars(select(AlphaScannedToken.rejection_reasons))).all()

    return {
        "status": "active" if total_scanned else "no_scans_recorded",
        "plain_english": {
            "pipeline": "Alpha discovery has analyzed tokens." if total_scanned else "No analyzed token rows exist yet.",
            "signals": (
                "No alpha alerts have qualified yet; analyzed tokens are being rejected or monitored by score/risk rules."
                if not alerts_total
                else "At least one alpha alert has qualified."
            ),
            "dedupe": (
                "A manual scan can return scanned=0 when the latest provider launches were already scanned inside the "
                f"{settings.new_pair_lookback_minutes}-minute dedupe window."
            ),
        },
        "scheduler": {
            "scan_interval_seconds": settings.alpha_scan_interval_seconds,
            "new_pair_lookback_minutes": settings.new_pair_lookback_minutes,
            "launch_scan_limit": settings.alpha_launch_scan_limit,
        },
        "thresholds": {
            "min_liquidity_usd": settings.alpha_min_liquidity_usd,
            "min_tx_count": settings.alpha_min_tx_count,
            "watchlist_min_score": settings.alpha_watchlist_min_score,
            "min_alert_score": settings.alpha_min_final_alert_score,
            "smart_wallet_min_count": settings.alpha_smart_wallet_min_count,
        },
        "telegram_noise_control": {
            "send_monitor_only_digest": settings.send_monitor_only_digest,
            "send_watchlist_digest": settings.send_watchlist_digest,
            "max_digest_tokens": settings.max_digest_tokens,
        },
        "counts": {
            "analyzed_tokens": total_scanned or 0,
            "alerts": alerts_total or 0,
            "decisions": {decision or "UNKNOWN": count for decision, count in decisions},
            "watchlist": {decision or "UNKNOWN": count for decision, count in watchlist_decisions},
        },
        "latest_seen_at": latest_seen.isoformat() if latest_seen else None,
        "top_rejection_reasons": _reason_summary(reason_rows),
        "provider_snapshots": [
            {
                "provider": provider,
                "snapshots": count,
                "latest_snapshot_at": latest.isoformat() if latest else None,
            }
            for provider, count, latest in provider_rows
        ],
    }


@router.get("/audit")
async def alpha_discovery_audit() -> dict[str, Any]:
    return ALPHA_DISCOVERY_AUDIT


@router.post("/report")
async def send_alpha_report() -> dict[str, Any]:
    return await send_alpha_discovery_report()


@router.post("/watchlist-digest")
async def send_watchlist_digest() -> dict[str, int]:
    return await send_alpha_watchlist_digest()


@router.get("/controls")
async def alpha_controls() -> dict[str, Any]:
    settings = get_settings()
    return {
        "mode": "alert_only",
        "scan_interval_seconds": settings.alpha_scan_interval_seconds,
        "report_interval_seconds": settings.alpha_report_interval_seconds,
        "launch_scan_limit": settings.alpha_launch_scan_limit,
        "min_liquidity_usd": settings.alpha_min_liquidity_usd,
        "max_initial_market_cap_usd": settings.alpha_max_initial_market_cap_usd,
        "min_tx_count": settings.alpha_min_tx_count,
        "watchlist_min_score": settings.alpha_watchlist_min_score,
        "min_alert_score": settings.alpha_min_final_alert_score,
        "smart_wallet_min_count": settings.alpha_smart_wallet_min_count,
        "smart_wallet_lookback_hours": settings.alpha_smart_wallet_lookback_hours,
        "telegram_alerts_enabled": settings.telegram_alerts_enabled,
        "send_monitor_only_digest": settings.send_monitor_only_digest,
        "send_watchlist_digest": settings.send_watchlist_digest,
        "max_digest_tokens": settings.max_digest_tokens,
        "discord_alerts_enabled": settings.discord_alerts_enabled,
        "debug_alpha_engine": settings.debug_alpha_engine,
        "safety": ALPHA_DISCOVERY_AUDIT["safety_boundaries"],
    }
