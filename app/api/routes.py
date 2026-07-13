from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.database.health import check_database
from app.database.session import engine
from app.integrations.health import integration_status

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    database_ok = await check_database(engine)
    settings = get_settings()
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
    ready_now = database_ok
    if not ready_now:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready_now else "not_ready",
        "database": database_ok,
        "runtime": "reset",
        "market_scanners_active": False,
        "signal_engines_active": False,
        "automatic_alerts_active": False,
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
