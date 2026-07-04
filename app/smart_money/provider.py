from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.core.config import Settings
from app.services.http import AsyncAPIClient


class WalletTransfer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    signature: str
    token_address: str
    token_symbol: str = "UNKNOWN"
    transaction_type: str = "swap"
    amount: Decimal = Decimal("0")
    usd_value: Decimal | None = None
    timestamp: datetime


class TokenMarketData(BaseModel):
    token_address: str
    token_symbol: str = "UNKNOWN"
    liquidity_usd: Decimal | None = None
    volume_24h_usd: Decimal | None = None
    market_cap_usd: Decimal | None = None
    age_hours: Decimal | None = None
    holder_count: int | None = None
    risk_flags: int = 0


class BlockchainProvider(ABC):
    chain: str

    @abstractmethod
    async def wallet_transfers(self, wallet_address: str, limit: int = 50) -> list[WalletTransfer]:
        raise NotImplementedError

    @abstractmethod
    async def token_market_data(self, token_address: str, token_symbol: str = "UNKNOWN") -> TokenMarketData:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


class SolanaProvider(BlockchainProvider):
    chain = "solana"

    def __init__(
        self,
        settings: Settings,
        moralis_client: AsyncAPIClient | None = None,
        dexscreener_client: AsyncAPIClient | None = None,
    ) -> None:
        self.settings = settings
        self.moralis_client = moralis_client or AsyncAPIClient(
            "https://solana-gateway.moralis.io",
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
            headers={"accept": "application/json", "X-API-Key": settings.moralis_api_key or ""},
        )
        self.dexscreener_client = dexscreener_client or AsyncAPIClient(
            "https://api.dexscreener.com",
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )

    async def wallet_transfers(self, wallet_address: str, limit: int = 50) -> list[WalletTransfer]:
        if not self.settings.moralis_api_key:
            return []
        payload = await self.moralis_client.request_json(
            "GET",
            f"/account/mainnet/{wallet_address}/transfers",
            params={"limit": limit},
            headers={"X-API-Key": self.settings.moralis_api_key},
        )
        raw_items = payload.get("result", payload) if isinstance(payload, dict) else payload
        if not isinstance(raw_items, list):
            return []
        return [self._normalize_transfer(item) for item in raw_items if self._has_token(item)]

    async def token_market_data(self, token_address: str, token_symbol: str = "UNKNOWN") -> TokenMarketData:
        payload = await self.dexscreener_client.request_json("GET", f"/latest/dex/tokens/{token_address}")
        pairs = payload.get("pairs", []) if isinstance(payload, dict) else []
        pair = pairs[0] if pairs else {}
        liquidity = pair.get("liquidity") or {}
        volume = pair.get("volume") or {}
        base_token = pair.get("baseToken") or {}
        return TokenMarketData(
            token_address=token_address,
            token_symbol=base_token.get("symbol") or token_symbol,
            liquidity_usd=self._decimal_or_none(liquidity.get("usd")),
            volume_24h_usd=self._decimal_or_none(volume.get("h24")),
            market_cap_usd=self._decimal_or_none(pair.get("marketCap") or pair.get("fdv")),
            age_hours=self._pair_age_hours(pair),
            holder_count=None,
            risk_flags=0,
        )

    @staticmethod
    def _has_token(item: dict[str, Any]) -> bool:
        return bool(
            item.get("mint")
            or item.get("token_address")
            or item.get("tokenAddress")
            or item.get("tokenMint")
            or item.get("address")
        )

    @classmethod
    def _normalize_transfer(cls, item: dict[str, Any]) -> WalletTransfer:
        timestamp_raw = item.get("blockTimestamp") or item.get("block_timestamp") or item.get("timestamp")
        if isinstance(timestamp_raw, str):
            timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
        else:
            timestamp = datetime.fromtimestamp(int(timestamp_raw or datetime.now(timezone.utc).timestamp()), tz=timezone.utc)
        amount = cls._decimal_or_zero(item.get("amount") or item.get("value") or item.get("tokenAmount"))
        usd_value = cls._decimal_or_none(item.get("usdValue") or item.get("usd_value") or item.get("valueUsd"))
        return WalletTransfer(
            signature=str(item.get("signature") or item.get("transactionHash") or item.get("transaction_hash")),
            token_address=str(
                item.get("mint")
                or item.get("token_address")
                or item.get("tokenAddress")
                or item.get("tokenMint")
                or item.get("address")
            ),
            token_symbol=str(item.get("symbol") or item.get("tokenSymbol") or item.get("token_symbol") or "UNKNOWN"),
            transaction_type=str(item.get("type") or item.get("transactionType") or "transfer").lower(),
            amount=amount,
            usd_value=usd_value,
            timestamp=timestamp,
        )

    @staticmethod
    def _decimal_or_zero(value: Any) -> Decimal:
        if value is None or value == "":
            return Decimal("0")
        return Decimal(str(value))

    @staticmethod
    def _decimal_or_none(value: Any) -> Decimal | None:
        if value is None or value == "":
            return None
        return Decimal(str(value))

    @staticmethod
    def _pair_age_hours(pair: dict[str, Any]) -> Decimal | None:
        created_at = pair.get("pairCreatedAt")
        if created_at is None:
            return None
        created = datetime.fromtimestamp(int(created_at) / 1000, tz=timezone.utc)
        return Decimal(str((datetime.now(timezone.utc) - created).total_seconds() / 3600))

    async def close(self) -> None:
        await self.moralis_client.close()
        await self.dexscreener_client.close()

