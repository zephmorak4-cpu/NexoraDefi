from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.http import AsyncAPIClient

logger = get_logger(__name__)


class TelegramClient:
    def __init__(self, token: str, client: AsyncAPIClient | None = None) -> None:
        self.token = token
        self.client = client or AsyncAPIClient(f"https://api.telegram.org/bot{token}")

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "Markdown",
        disable_web_page_preview: bool = True,
    ) -> dict[str, Any]:
        payload = await self.client.request_json(
            "POST",
            "/sendMessage",
            data={
                "chat_id": chat_id,
                "text": text[:4096],
                "parse_mode": parse_mode,
                "disable_web_page_preview": str(disable_web_page_preview).lower(),
            },
        )
        if not payload.get("ok", False):
            logger.warning("telegram_send_failed", description=payload.get("description"))
        return payload

    async def close(self) -> None:
        await self.client.close()
