from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.database.health import check_database
from app.database.session import engine

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(response: Response) -> dict[str, object]:
    database_ok = await check_database(engine)
    settings = get_settings()
    required_credentials = {
        "blockchain": settings.moralis_api_key or settings.etherscan_api_key,
        "telegram": settings.telegram_bot_token and settings.telegram_chat_id,
    }
    optional_credentials = {
        "coingecko": settings.coingecko_api_key,
        "reddit": settings.reddit_client_id and settings.reddit_client_secret,
        "cryptopanic": settings.cryptopanic_api_key,
        "openai": settings.openai_api_key if settings.analyst_provider == "openai" else True,
    }
    credentials_ok = all(required_credentials.values())
    ready_now = database_ok and (settings.app_env != "production" or credentials_ok)
    if not ready_now:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready_now else "not_ready",
        "database": database_ok,
        "collectors_configured": credentials_ok,
        "required_credentials": {name: bool(value) for name, value in required_credentials.items()},
        "optional_credentials": {name: bool(value) for name, value in optional_credentials.items()},
    }
