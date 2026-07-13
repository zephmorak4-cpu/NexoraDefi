from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.integrations.market_data_clients import DexScreenerClient, GeckoTerminalClient
from app.spot.types import Candle, MarketQuote, TokenAsset


STABLE_SYMBOLS = {"USDC", "USDT", "DAI", "USDH", "PYUSD", "UXD"}
WRAPPED_SYMBOLS = {"WSOL", "WETH", "WBTC"}


def number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        result = float(value)
        return result if result >= 0 else None
    except (TypeError, ValueError):
        return None


def unix_ms_to_datetime(value: Any) -> datetime | None:
    try:
        if value in (None, ""):
            return None
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


class MarketDataGateway:
    def __init__(
        self,
        settings: Settings,
        dexscreener: DexScreenerClient | None = None,
        geckoterminal: GeckoTerminalClient | None = None,
    ) -> None:
        self.settings = settings
        self.dexscreener = dexscreener or DexScreenerClient(settings)
        self.geckoterminal = geckoterminal or GeckoTerminalClient(settings)

    async def discover_solana_candidates(self) -> list[TokenAsset]:
        profiles = await self.dexscreener.request("/token-profiles/latest/v1")
        tokens: dict[str, TokenAsset] = {}
        for profile in profiles if isinstance(profiles, list) else []:
            if not isinstance(profile, dict) or profile.get("chainId") != "solana":
                continue
            token_address = str(profile.get("tokenAddress") or "")
            if not token_address:
                continue
            pairs = await self.dexscreener.request(f"/token-pairs/v1/solana/{token_address}")
            for pair in pairs if isinstance(pairs, list) else []:
                asset = self._asset_from_dex_pair(pair)
                if asset and (asset.address not in tokens or (asset.liquidity_usd or 0) > (tokens[asset.address].liquidity_usd or 0)):
                    tokens[asset.address] = asset
        if len(tokens) < self.settings.candidate_universe_size:
            for asset in await self._gecko_candidates():
                if asset.address not in tokens:
                    tokens[asset.address] = asset
        return list(tokens.values())

    async def _gecko_candidates(self) -> list[TokenAsset]:
        payload = await self.geckoterminal.network_pools(page=1)
        assets: list[TokenAsset] = []
        for item in payload.get("data", []) if isinstance(payload, dict) else []:
            attributes = item.get("attributes") or {}
            relationships = item.get("relationships") or {}
            base = (relationships.get("base_token", {}).get("data") or {}).get("id", "")
            token_address = str(base).split("_")[-1] if base else str(attributes.get("address") or "")
            name = str(attributes.get("name") or "UNKNOWN")
            symbol = name.split("/")[0].strip()[:32] or "UNKNOWN"
            assets.append(
                TokenAsset(
                    chain="solana",
                    address=token_address,
                    symbol=symbol,
                    name=name[:128],
                    liquidity_usd=number(attributes.get("reserve_in_usd")),
                    volume_24h_usd=number((attributes.get("volume_usd") or {}).get("h24")),
                    primary_pool_address=str(item.get("id") or "").split("_")[-1],
                    primary_dex=str(attributes.get("dex_id") or "geckoterminal"),
                    data_sources=["GeckoTerminal"],
                )
            )
        return [asset for asset in assets if asset.address]

    async def candles(self, token: TokenAsset, timeframe: str, limit: int = 200) -> list[Candle]:
        if not token.primary_pool_address:
            return []
        gecko_timeframe, aggregate = self._timeframe(timeframe)
        payload = await self.geckoterminal.ohlcv(token.primary_pool_address, gecko_timeframe, aggregate, limit)
        ohlcv = (((payload or {}).get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
        candles: list[Candle] = []
        for row in ohlcv:
            if not isinstance(row, list) or len(row) < 6:
                continue
            timestamp = datetime.fromtimestamp(int(row[0]), tz=timezone.utc)
            candle = Candle(
                token_address=token.address,
                pool_address=token.primary_pool_address,
                timeframe=timeframe,
                timestamp=timestamp,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
                source="GeckoTerminal",
                is_closed=True,
            )
            candles.append(candle)
        return sorted(candles, key=lambda candle: candle.timestamp)

    async def quote(self, token: TokenAsset) -> MarketQuote | None:
        if not token.primary_pool_address:
            return None
        payload = await self.dexscreener.request(f"/latest/dex/pairs/solana/{token.primary_pool_address}")
        pairs = payload.get("pairs") if isinstance(payload, dict) else None
        pair = pairs[0] if isinstance(pairs, list) and pairs else None
        if not isinstance(pair, dict):
            return None
        price = number(pair.get("priceUsd"))
        if not price or price <= 0:
            return None
        return MarketQuote(
            token_address=token.address,
            price_usd=price,
            liquidity_usd=number((pair.get("liquidity") or {}).get("usd")),
            timestamp=datetime.now(timezone.utc),
            source="DEX Screener",
        )

    @staticmethod
    def _timeframe(timeframe: str) -> tuple[str, int]:
        if timeframe == "15m":
            return "minute", 15
        if timeframe == "1h":
            return "hour", 1
        if timeframe == "4h":
            return "hour", 4
        raise ValueError(f"unsupported timeframe: {timeframe}")

    @staticmethod
    def _asset_from_dex_pair(pair: dict[str, Any]) -> TokenAsset | None:
        if not isinstance(pair, dict) or pair.get("chainId") != "solana":
            return None
        base = pair.get("baseToken") or {}
        quote = pair.get("quoteToken") or {}
        symbol = str(base.get("symbol") or "UNKNOWN").upper()
        if symbol in STABLE_SYMBOLS or symbol in WRAPPED_SYMBOLS:
            return None
        address = str(base.get("address") or "")
        if not address:
            return None
        return TokenAsset(
            chain="solana",
            address=address,
            symbol=symbol[:32],
            name=str(base.get("name") or symbol)[:128],
            created_at=unix_ms_to_datetime(pair.get("pairCreatedAt")),
            market_cap_usd=number(pair.get("marketCap")),
            fdv_usd=number(pair.get("fdv")),
            liquidity_usd=number((pair.get("liquidity") or {}).get("usd")),
            volume_24h_usd=number((pair.get("volume") or {}).get("h24")),
            primary_pool_address=str(pair.get("pairAddress") or ""),
            primary_dex=str(pair.get("dexId") or ""),
            quote_asset=str(quote.get("symbol") or ""),
            data_sources=["DEX Screener"],
        )

    async def close(self) -> None:
        await self.dexscreener.close()
        await self.geckoterminal.close()

