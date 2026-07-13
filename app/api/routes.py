import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import desc, select

from app.core.config import get_settings
from app.database.health import check_database
from app.database.session import SessionFactory, engine
from app.integrations.health import integration_status
from app.models import SpotUniverseSnapshot
from app.spot.job_state import build_version
from app.spot.providers import ProviderCapabilityService

router = APIRouter()
STARTED_AT = time.monotonic()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live")
async def health_live() -> dict[str, object]:
    return {
        "status": "alive",
        "service": "solana-spot-momentum-engine",
        "buildVersion": build_version(),
        "uptimeSeconds": int(time.monotonic() - STARTED_AT),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _latest_universe_status() -> dict[str, object]:
    async with SessionFactory() as session:
        snapshot = await session.scalar(
            select(SpotUniverseSnapshot).order_by(desc(SpotUniverseSnapshot.created_at)).limit(1)
        )
    if snapshot is None:
        return {"status": "missing", "core_count": 0, "snapshot_id": None}
    return {
        "status": "healthy" if snapshot.core_count > 0 else "missing_core",
        "core_count": snapshot.core_count,
        "snapshot_id": snapshot.snapshot_id,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }


@router.get("/health/ready")
async def health_ready(request: Request, response: Response) -> dict[str, object]:
    settings = get_settings()
    database_ok = await check_database(engine)
    universe = await _latest_universe_status() if database_ok else {"status": "unavailable", "core_count": 0}
    scheduler_ready = bool(getattr(request.app.state, "scheduler", None))
    telegram_ready = bool(settings.telegram_bot_token and settings.telegram_chat_id) if settings.telegram_signals_enabled else True
    provider_audit = await ProviderCapabilityService(settings).audit(live=True)
    ready_now = (
        database_ok
        and universe["status"] == "healthy"
        and scheduler_ready
        and telegram_ready
        and not provider_audit.missing_capabilities
    )
    if not ready_now:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready_now else "not_ready",
        "database": "healthy" if database_ok else "offline",
        "universe": universe,
        "providers": "configured" if not provider_audit.missing_capabilities else "missing_capabilities",
        "missing_capabilities": provider_audit.missing_capabilities,
        "telegram": "healthy" if telegram_ready else "not_configured",
        "scheduler": "initialized" if scheduler_ready else "not_initialized",
        "trading_mode": "PAPER_ONLY",
        "live_trading": "DISABLED",
    }


@router.get("/health/details")
async def health_details(request: Request, response: Response) -> dict[str, object]:
    ready = await health_ready(request, response)
    settings = get_settings()
    database_url = settings.database_url
    durable_database = not database_url.startswith("sqlite")
    return {
        **ready,
        "runtime": {
            "product": "Solana Spot Momentum Engine",
            "universe_mode": "ESTABLISHED_ASSETS",
            "strategy": settings.strategy_version,
            "buildVersion": build_version(),
            "render": bool(os.getenv("RENDER")),
        },
        "persistence": {
            "database_type": "postgresql" if durable_database else "sqlite",
            "durable_for_render": durable_database,
            "connection_string_exposed": False,
        },
        "safety": {
            "live_buying": "NOT_IMPLEMENTED",
            "live_selling": "NOT_IMPLEMENTED",
            "wallet_signing": "NOT_IMPLEMENTED",
            "private_keys": "NOT_IMPLEMENTED",
            "futures_leverage": "NOT_IMPLEMENTED",
        },
    }


@router.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    database_ok = await check_database(engine)
    settings = get_settings()
    provider_audit = await ProviderCapabilityService(settings).audit(live=True)
    required_credentials = {
        "database": database_ok,
    }
    optional_credentials = {
        "telegram": settings.telegram_bot_token and settings.telegram_chat_id,
        "discord": settings.discord_webhook_url,
        "solana_rpc": settings.solana_rpc_url,
        "helius": settings.helius_api_key,
        "birdeye": settings.birdeye_api_key,
        "dexscreener": settings.dexscreener_enabled,
        "moralis": settings.moralis_api_key,
        "etherscan": settings.etherscan_api_key,
        "coingecko": settings.coingecko_api_key,
        "reddit": settings.reddit_client_id and settings.reddit_client_secret,
        "cryptopanic": settings.cryptopanic_api_key,
        "openai": settings.openai_api_key if settings.analyst_provider == "openai" else True,
    }
    credentials_ok = all(required_credentials.values())
    ready_now = database_ok and not provider_audit.missing_capabilities
    if not ready_now:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready_now else "not_ready",
        "readiness_state": provider_audit.state.value if database_ok else "NOT_READY",
        "database": database_ok,
        "runtime": "spot_momentum_paper_trading",
        "market_scanners_active": settings.scheduler_enabled and settings.paper_trading_enabled,
        "signal_engines_active": settings.paper_trading_enabled,
        "automatic_alerts_active": settings.telegram_signals_enabled,
        "missing_capabilities": provider_audit.missing_capabilities,
        "required_credentials": {name: bool(value) for name, value in required_credentials.items()},
        "optional_credentials": {name: bool(value) for name, value in optional_credentials.items()},
    }


@router.get("/integrations/health")
async def integrations_health() -> dict[str, object]:
    database_ok = await check_database(engine)
    settings = get_settings()
    return {
        "status": "ok" if database_ok else "degraded",
        "checks": integration_status(settings, database_ok),
        "note": "Configuration-only check; no messages, market scans, signals, or trades are triggered.",
    }
