from __future__ import annotations

from pathlib import Path
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

    async def send_document(
        self,
        chat_id: int,
        document_path: str | Path,
        caption: str | None = None,
        parse_mode: str = "Markdown",
    ) -> dict[str, Any]:
        path = Path(document_path)
        with path.open("rb") as file_handle:
            response = await self.client.client.post(
                "/sendDocument",
                data={
                    "chat_id": chat_id,
                    "caption": (caption or "")[:1024],
                    "parse_mode": parse_mode,
                },
                files={"document": (path.name, file_handle, self._content_type(path))},
            )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok", False):
            logger.warning("telegram_document_send_failed", description=payload.get("description"))
        return payload

    @staticmethod
    def _content_type(path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            return "application/pdf"
        if path.suffix.lower() == ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return "application/octet-stream"

    async def close(self) -> None:
        await self.client.close()
