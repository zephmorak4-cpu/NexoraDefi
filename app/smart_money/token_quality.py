from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TokenQuality
from app.smart_money.provider import BlockchainProvider, TokenMarketData
from app.smart_money.wallet_reputation import clamp


class TokenQualityEngine:
    def __init__(self, session: AsyncSession, provider: BlockchainProvider) -> None:
        self.session = session
        self.provider = provider

    async def recalculate(self, token_address: str, token_symbol: str = "UNKNOWN") -> TokenQuality:
        data = await self.provider.token_market_data(token_address, token_symbol)
        quality = await self.session.scalar(select(TokenQuality).where(TokenQuality.token_address == token_address))
        if quality is None:
            quality = TokenQuality(token_address=token_address, token_symbol=token_symbol)
            self.session.add(quality)
            await self.session.flush()
        scores = self.score_market_data(data)
        quality.token_symbol = data.token_symbol
        quality.liquidity_score = scores["liquidity"]
        quality.volume_score = scores["volume"]
        quality.holder_score = scores["holders"]
        quality.age_score = scores["age"]
        quality.market_cap_score = scores["market_cap"]
        quality.risk_score = scores["risk"]
        quality.quality_score = scores["quality"]
        return quality

    @staticmethod
    def score_market_data(data: TokenMarketData) -> dict[str, Decimal]:
        liquidity = clamp((data.liquidity_usd or Decimal("0")) / Decimal("1000"))
        volume = clamp((data.volume_24h_usd or Decimal("0")) / Decimal("2000"))
        holders = clamp(Decimal(str(data.holder_count or 0)) / Decimal("10"))
        age = clamp((data.age_hours or Decimal("0")) / Decimal("24"))
        market_cap = clamp((data.market_cap_usd or Decimal("0")) / Decimal("10000"))
        risk = clamp(Decimal("100") - Decimal(str(data.risk_flags * 20)))
        quality = clamp(
            liquidity * Decimal("0.30")
            + volume * Decimal("0.20")
            + holders * Decimal("0.10")
            + age * Decimal("0.10")
            + market_cap * Decimal("0.20")
            + risk * Decimal("0.10")
        )
        return {
            "liquidity": liquidity,
            "volume": volume,
            "holders": holders,
            "age": age,
            "market_cap": market_cap,
            "risk": risk,
            "quality": quality,
        }

