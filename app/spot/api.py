from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.config import get_settings
from app.database.health import check_database
from app.database.session import SessionFactory, engine
from app.spot.engine import SpotMomentumEngine
from app.spot.notifications import SignalNotificationService
from app.spot.providers import ProviderCapabilityService
from app.spot.repositories import SpotRepository

router = APIRouter(prefix="/spot", tags=["spot-momentum"])


@router.get("/status")
async def system_status(live: bool = Query(False)) -> dict[str, object]:
    settings = get_settings()
    database_ok = await check_database(engine)
    async with SessionFactory() as session:
        audit = await ProviderCapabilityService(settings).audit(session=session, live=live)
    return {
        "state": audit.state.value if database_ok else "NOT_READY",
        "database": "HEALTHY" if database_ok else "OFFLINE",
        "missing_capabilities": audit.missing_capabilities,
        "providers": [
            {
                "provider": check.provider,
                "capability": check.capability,
                "status": check.status.value,
                "latency_ms": check.latency_ms,
                "action": check.action,
            }
            for check in audit.checks
        ],
        "safety": {
            "paper_trading_enabled": settings.paper_trading_enabled,
            "live_trading_enabled": settings.live_trading_enabled,
            "auto_buying": "NOT_IMPLEMENTED",
            "auto_selling": "NOT_IMPLEMENTED",
            "wallet_signing": "NOT_IMPLEMENTED",
        },
    }


@router.post("/universe/build")
async def build_universe() -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        engine_instance = SpotMomentumEngine(settings)
        try:
            return await engine_instance.build_universe(session)
        finally:
            await engine_instance.close()


@router.post("/market/refresh")
async def refresh_market_data() -> dict[str, int]:
    settings = get_settings()
    async with SessionFactory() as session:
        engine_instance = SpotMomentumEngine(settings)
        try:
            return await engine_instance.refresh_market_data(session)
        finally:
            await engine_instance.close()


@router.post("/scan")
async def scan_once(notify: bool = Query(False)) -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        engine_instance = SpotMomentumEngine(settings)
        try:
            return await engine_instance.scan_once(session, notify=notify)
        finally:
            await engine_instance.close()


@router.get("/scan/funnel")
async def scan_funnel() -> dict[str, object]:
    async with SessionFactory() as session:
        return await SpotRepository(session).latest_scan_funnel()


@router.get("/scan/evaluations")
async def scan_evaluations(limit: int = Query(100, ge=1, le=250)) -> dict[str, object]:
    async with SessionFactory() as session:
        return await SpotRepository(session).latest_scan_evaluations(limit=limit)


@router.get("/universe/members")
async def universe_members(tier: str | None = Query(None), limit: int = Query(100, ge=1, le=500)) -> dict[str, object]:
    async with SessionFactory() as session:
        members = await SpotRepository(session).latest_universe_members(tier=tier, limit=limit)
    return {"count": len(members), "members": members}


@router.get("/universe/candle-coverage")
async def universe_candle_coverage(limit: int = Query(100, ge=1, le=250)) -> dict[str, object]:
    async with SessionFactory() as session:
        coverage = await SpotRepository(session).core_candle_coverage(limit=limit)
    return {"count": len(coverage), "coverage": coverage}


@router.post("/telegram/test")
async def telegram_test() -> dict[str, bool]:
    settings = get_settings()
    service = SignalNotificationService(settings)
    try:
        return {"sent": await service.send_test_message()}
    finally:
        await service.close()
