import re
from base64 import b64encode
from collections import Counter
from datetime import datetime, timezone

from app.collectors.base import BaseCollector
from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.records import SocialRecord
from app.services.http import AsyncAPIClient

logger = get_logger(__name__)
WORD = re.compile(r"\b[a-zA-Z][a-zA-Z0-9-]{1,20}\b")


class SocialCollector(BaseCollector):
    def __init__(self, session, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        super().__init__(session, client or AsyncAPIClient("https://www.reddit.com", timeout=settings.http_timeout_seconds, max_retries=settings.http_max_retries, headers={"User-Agent": "nexora-data/0.1"}))

    async def _access_token(self) -> str | None:
        if not self.settings.reddit_client_id or not self.settings.reddit_client_secret:
            logger.info("collector_skipped", collector="social", reason="missing_api_credentials")
            return None
        credentials = f"{self.settings.reddit_client_id}:{self.settings.reddit_client_secret}"
        payload = await self.client.request_json(
            "POST",
            "https://www.reddit.com/api/v1/access_token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {b64encode(credentials.encode()).decode()}"},
        )
        return payload["access_token"]

    @staticmethod
    def trending_topics(posts: list[dict], limit: int = 20) -> list[tuple[str, int]]:
        counts: Counter[str] = Counter()
        for post in posts:
            text = f"{post.get('title', '')} {post.get('selftext', '')}".lower()
            counts.update(word for word in WORD.findall(text) if len(word) > 2)
        return counts.most_common(limit)

    async def collect(self) -> int:
        token = await self._access_token()
        if not token:
            return 0
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        all_posts: list[dict] = []
        for subreddit in self.settings.reddit_subreddits:
            payload = await self.client.request_json(
                "GET", f"https://oauth.reddit.com/r/{subreddit}/new", params={"limit": 100}, headers={"Authorization": f"Bearer {token}"},
            )
            all_posts.extend(child["data"] for child in payload.get("data", {}).get("children", []))
        stored = 0
        for coin_id in self.settings.tracked_coins:
            needle = coin_id.replace("-", " ").lower()
            mentions = sum(f"{post.get('title', '')} {post.get('selftext', '')}".lower().count(needle) for post in all_posts)
            record = SocialRecord(coin_id=coin_id, symbol=coin_id[:10], name=coin_id.replace("-", " ").title(), source="reddit", mentions=mentions, timestamp=now)
            stored += int(await self.repository.add_social(record))
        await self.session.commit()
        logger.info("collector_complete", collector="social", stored=stored, topics=self.trending_topics(all_posts, 5))
        return stored
