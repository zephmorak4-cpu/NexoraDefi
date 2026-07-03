from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import ValidationError

from app.collectors.base import BaseCollector
from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.records import PriceRecord
from app.services.http import AsyncAPIClient

logger = get_logger(__name__)


class MarketCollector(BaseCollector):
    def __init__(self, session, settings: Settings, client: AsyncAPIClient | None = None) -> None:
        self.settings = settings
        headers = {"x-cg-demo-api-key": settings.coingecko_api_key} if settings.coingecko_api_key else {}
        super().__init__(
            session,
            client or AsyncAPIClient("https://api.coingecko.com/api/v3", timeout=settings.http_timeout_seconds, max_retries=settings.http_max_retries, headers=headers),
        )

    @staticmethod
    def normalize_current(coin_id: str, item: dict[str, Any], timestamp: datetime) -> PriceRecord:
        price = item.get("current_price", item.get("usd"))
        market_cap = item.get("market_cap", item.get("usd_market_cap"))
        volume = item.get("total_volume", item.get("usd_24h_vol"))
        return PriceRecord(
            coin_id=coin_id,
            symbol=str(item.get("symbol", coin_id[:10])).upper(),
            name=str(item.get("name", coin_id.replace("-", " ").title())),
            price=Decimal(str(price)),
            market_cap=Decimal(str(market_cap)) if market_cap is not None else None,
            volume=Decimal(str(volume)) if volume is not None else None,
            liquidity_value=Decimal(str(item["liquidity_value"])) if item.get("liquidity_value") is not None else None,
            timestamp=timestamp,
        )

    async def collect(self) -> int:
        if not self.settings.tracked_coins:
            return 0
        payload = await self.client.request_json(
            "GET", "/coins/markets",
            params={
                "ids": ",".join(self.settings.tracked_coins),
                "vs_currency": "usd",
                "price_change_percentage": "1h,24h,7d,30d",
            },
        )
        stored = 0
        items = (
            [(str(item["id"]), item) for item in payload]
            if isinstance(payload, list)
            else list(payload.items())
        )
        for coin_id, item in items:
            try:
                raw_timestamp = item.get("last_updated") or item.get("last_updated_at")
                if isinstance(raw_timestamp, str):
                    timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
                else:
                    timestamp = datetime.fromtimestamp(raw_timestamp or datetime.now(timezone.utc).timestamp(), tz=timezone.utc)
                record = self.normalize_current(coin_id, item, timestamp)
                stored += int(await self.repository.add_price(record))
            except (KeyError, ValueError, ValidationError) as exc:
                logger.warning("invalid_market_record", coin_id=coin_id, error=str(exc))
        await self.session.commit()
        logger.info("collector_complete", collector="market", stored=stored)
        return stored

    async def collect_history(self, coin_id: str, days: int = 1) -> int:
        payload = await self.client.request_json("GET", f"/coins/{coin_id}/market_chart", params={"vs_currency": "usd", "days": days})
        caps = {point[0]: point[1] for point in payload.get("market_caps", [])}
        volumes = {point[0]: point[1] for point in payload.get("total_volumes", [])}
        stored = 0
        for epoch_ms, price in payload.get("prices", []):
            record = PriceRecord(
                coin_id=coin_id, symbol=coin_id[:10], name=coin_id.replace("-", " ").title(),
                price=Decimal(str(price)), market_cap=Decimal(str(caps[epoch_ms])) if epoch_ms in caps else None,
                volume=Decimal(str(volumes[epoch_ms])) if epoch_ms in volumes else None,
                liquidity_value=None,
                timestamp=datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc),
            )
            stored += int(await self.repository.add_price(record))
        await self.session.commit()
        return stored
