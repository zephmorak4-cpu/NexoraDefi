from datetime import datetime

from pydantic import ValidationError

from app.collectors.base import BaseCollector
from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.records import NewsRecord
from app.services.http import AsyncAPIClient

logger = get_logger(__name__)


class NewsCollector(BaseCollector):
    def __init__(self, session, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        super().__init__(session, client or AsyncAPIClient("https://cryptopanic.com/api/developer/v2", timeout=settings.http_timeout_seconds, max_retries=settings.http_max_retries))

    @staticmethod
    def normalize(item: dict) -> NewsRecord:
        votes = item.get("votes") or {}
        sentiment = None
        if votes:
            positive = int(votes.get("positive", 0)) + int(votes.get("liked", 0))
            negative = int(votes.get("negative", 0)) + int(votes.get("disliked", 0))
            sentiment = "positive" if positive > negative else "negative" if negative > positive else "neutral"
        return NewsRecord(
            external_id=str(item["id"]), title=item["title"], url=item["url"],
            source=(item.get("source") or {}).get("title"), sentiment=sentiment,
            published_at=datetime.fromisoformat(item["published_at"].replace("Z", "+00:00")),
        )

    async def collect(self) -> int:
        if not self.settings.cryptopanic_api_key:
            logger.info("collector_skipped", collector="news", reason="missing_api_key")
            return 0
        payload = await self.client.request_json("GET", "/posts/", params={"auth_token": self.settings.cryptopanic_api_key, "public": "true"})
        stored = 0
        for item in payload.get("results", []):
            try:
                stored += int(await self.repository.add_news(self.normalize(item)))
            except (KeyError, ValueError, ValidationError) as exc:
                logger.warning("invalid_news_record", error=str(exc))
        await self.session.commit()
        logger.info("collector_complete", collector="news", stored=stored)
        return stored
