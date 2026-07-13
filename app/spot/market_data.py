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
        profiles = await self._safe_dex_request("/token-profiles/latest/v1") or []
        tokens: dict[str, TokenAsset] = {}
        for profile in profiles if isinstance(profiles, list) else []:
            if not isinstance(profile, dict) or profile.get("chainId") != "solana":
                continue
            token_address = str(profile.get("tokenAddress") or "")
            if not token_address:
                continue
            pairs = await self._safe_dex_request(f"/token-pairs/v1/solana/{token_address}") or []
            for pair in pairs if isinstance(pairs, list) else []:
                asset = self._asset_from_dex_pair(pair)
                if asset:
                    self._add_best(tokens, asset)
        for asset in await self._dex_search_candidates():
            self._add_best(tokens, asset)
        if len(tokens) < self.settings.candidate_universe_size:
            for asset in await self._gecko_candidates():
                self._add_best(tokens, asset)
        return list(tokens.values())

    async def _gecko_candidates(self) -> list[TokenAsset]:
        assets: list[TokenAsset] = []
        for page in range(1, self.settings.discovery_gecko_pages + 1):
            try:
                payload = await self.geckoterminal.network_pools(page=page)
            except Exception:
                continue
            for item in payload.get("data", []) if isinstance(payload, dict) else []:
                attributes = item.get("attributes") or {}
                relationships = item.get("relationships") or {}
                base = (relationships.get("base_token", {}).get("data") or {}).get("id", "")
                token_address = str(base).split("_")[-1] if base else str(attributes.get("address") or "")
                name = str(attributes.get("name") or "UNKNOWN")
                symbol = name.split("/")[0].strip().upper()[:32] or "UNKNOWN"
                quote_symbol = name.split("/")[-1].strip().upper()[:32] if "/" in name else None
                assets.append(
                    TokenAsset(
                        chain="solana",
                        address=token_address,
                        symbol=symbol,
                        name=name[:128],
                        market_cap_usd=number(attributes.get("market_cap_usd")),
                        fdv_usd=number(attributes.get("fdv_usd")),
                        liquidity_usd=number(attributes.get("reserve_in_usd")),
                        volume_24h_usd=number((attributes.get("volume_usd") or {}).get("h24")),
                        primary_pool_address=str(item.get("id") or "").split("_")[-1],
                        primary_dex=str(attributes.get("dex_id") or "geckoterminal"),
                        quote_asset=quote_symbol,
                        data_sources=["GeckoTerminal"],
                    )
                )
        return [asset for asset in assets if asset.address]

    async def _dex_search_candidates(self) -> list[TokenAsset]:
        queries = [item.strip() for item in self.settings.discovery_dex_search_queries.split(",") if item.strip()]
        assets: list[TokenAsset] = []
        for query in queries:
            payload = await self._safe_dex_request("/latest/dex/search", params={"q": query})
            pairs = payload.get("pairs") if isinstance(payload, dict) else None
            for pair in pairs if isinstance(pairs, list) else []:
                asset = self._asset_from_dex_pair(pair)
                if asset:
                    assets.append(asset)
        return assets

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

    async def _safe_dex_request(self, path: str, params: dict[str, Any] | None = None) -> Any | None:
        try:
            return await self.dexscreener.request(path, params=params)
        except Exception:
            return None

    @staticmethod
    def _add_best(tokens: dict[str, TokenAsset], asset: TokenAsset) -> None:
        existing = tokens.get(asset.address)
        if existing is None:
            tokens[asset.address] = asset
            return
        if (asset.liquidity_usd or 0) > (existing.liquidity_usd or 0):
            sources = sorted(set(existing.data_sources + asset.data_sources))
            tokens[asset.address] = TokenAsset(
                chain=asset.chain,
                address=asset.address,
                symbol=asset.symbol,
                name=asset.name,
                decimals=asset.decimals or existing.decimals,
                created_at=asset.created_at or existing.created_at,
                market_cap_usd=asset.market_cap_usd or existing.market_cap_usd,
                fdv_usd=asset.fdv_usd or existing.fdv_usd,
                liquidity_usd=asset.liquidity_usd or existing.liquidity_usd,
                volume_24h_usd=asset.volume_24h_usd or existing.volume_24h_usd,
                primary_pool_address=asset.primary_pool_address or existing.primary_pool_address,
                primary_dex=asset.primary_dex or existing.primary_dex,
                quote_asset=asset.quote_asset or existing.quote_asset,
                data_sources=sources,
            )
            return
        existing.data_sources.extend(source for source in asset.data_sources if source not in existing.data_sources)

    async def close(self) -> None:
        await self.dexscreener.close()
        await self.geckoterminal.close()
