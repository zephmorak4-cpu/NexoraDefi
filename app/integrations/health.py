from __future__ import annotations

from app.core.config import Settings


def integration_status(settings: Settings, database_ok: bool) -> dict[str, str]:
    return {
        "Telegram": _configured(bool(settings.telegram_bot_token and settings.telegram_chat_id)),
        "Discord": _configured(bool(settings.discord_webhook_url)),
        "OpenAI": _configured(bool(settings.openai_api_key)),
        "Solana RPC": _configured(bool(settings.solana_rpc_url)),
        "Helius": _configured(bool(settings.helius_api_key)),
        "Birdeye": _configured(bool(settings.birdeye_api_key)),
        "DEX Screener": "AVAILABLE" if settings.dexscreener_enabled else "DISABLED",
        "CoinGecko": _configured(bool(settings.coingecko_api_key)),
        "Moralis": _configured(bool(settings.moralis_api_key)),
        "Etherscan": _configured(bool(settings.etherscan_api_key)),
        "Database": "CONNECTED" if database_ok else "UNAVAILABLE",
    }


def _configured(value: bool) -> str:
    return "CONFIGURED" if value else "NOT_CONFIGURED"
