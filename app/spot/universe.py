from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import Settings
from app.spot.market_data import STABLE_SYMBOLS
from app.spot.types import TokenAsset


@dataclass(frozen=True)
class RankedToken:
    token: TokenAsset
    tier: str
    rank: int | None
    score: float
    reasons: list[str]
    factors: dict[str, float]


@dataclass(frozen=True)
class UniverseBuild:
    snapshot_id: str
    raw_candidates_retrieved: int
    eligible: list[RankedToken]
    core: list[RankedToken]
    candidate: list[RankedToken]
    excluded: list[RankedToken]
    exclusion_summary: list[dict[str, int]]


class TokenEligibilityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(self, token: TokenAsset) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if token.chain != "solana":
            reasons.append("not Solana")
        if token.symbol.upper() in STABLE_SYMBOLS:
            reasons.append("stablecoin excluded")
        if token.address.lower().endswith("pump") or token.symbol.upper() == "PUMP":
            reasons.append("pump.fun launch asset excluded")
        if token.created_at:
            age_days = (datetime.now(timezone.utc) - token.created_at).days
            if age_days < self.settings.min_token_age_days:
                reasons.append("insufficient age")
        if (token.liquidity_usd or 0) < self.settings.min_liquidity_usd:
            reasons.append("insufficient liquidity")
        if (token.volume_24h_usd or 0) < self.settings.min_volume_24h_usd:
            reasons.append("insufficient 24h volume")
        market_cap = token.market_cap_usd if token.market_cap_usd is not None else token.fdv_usd
        if market_cap is not None and market_cap < self.settings.min_market_cap_usd:
            reasons.append("insufficient market cap")
        if self.settings.max_market_cap_usd and market_cap is not None and market_cap > self.settings.max_market_cap_usd:
            reasons.append("market cap above maximum")
        if not token.primary_pool_address:
            reasons.append("missing primary pool")
        if token.quote_asset and token.quote_asset.upper() not in {"USDC", "SOL", "WSOL"}:
            reasons.append("unsupported quote asset")
        return not reasons, reasons


class TokenRankingService:
    def score(self, token: TokenAsset) -> tuple[float, dict[str, float]]:
        liquidity = min((token.liquidity_usd or 0) / 5_000_000, 1) * 25
        volume = min((token.volume_24h_usd or 0) / 10_000_000, 1) * 20
        market_cap = token.market_cap_usd if token.market_cap_usd is not None else token.fdv_usd
        market = min(((market_cap or 0) / 100_000_000), 1) * 15
        pool = 10 if token.primary_pool_address else 0
        continuity = 10
        volatility = 20
        factors = {
            "liquidity_quality": liquidity,
            "volume_quality": volume,
            "market_quality": market,
            "pool_quality": pool,
            "price_action_continuity": continuity,
            "tradable_volatility": volatility,
        }
        return round(sum(factors.values()), 4), factors


class UniverseBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.eligibility = TokenEligibilityService(settings)
        self.ranking = TokenRankingService()

    def build(self, tokens: list[TokenAsset]) -> UniverseBuild:
        eligible: list[RankedToken] = []
        excluded: list[RankedToken] = []
        for token in tokens:
            ok, reasons = self.eligibility.evaluate(token)
            score, factors = self.ranking.score(token)
            if ok:
                eligible.append(RankedToken(token, "ELIGIBLE", None, score, ["eligible"], factors))
            else:
                excluded.append(RankedToken(token, "EXCLUDED", None, score, reasons, factors))
        eligible = sorted(eligible, key=lambda item: item.score, reverse=True)
        core: list[RankedToken] = []
        candidate: list[RankedToken] = []
        for index, item in enumerate(eligible, start=1):
            if len(core) < self.settings.target_universe_size:
                core.append(RankedToken(item.token, "CORE", index, item.score, item.reasons, item.factors))
            elif len(candidate) < self.settings.candidate_universe_size:
                candidate.append(RankedToken(item.token, "CANDIDATE", index, item.score, item.reasons, item.factors))
        exclusions = Counter(reason for item in excluded for reason in item.reasons)
        return UniverseBuild(
            snapshot_id=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            raw_candidates_retrieved=len(tokens),
            eligible=eligible,
            core=core,
            candidate=candidate,
            excluded=excluded,
            exclusion_summary=[{"reason": reason, "count": count} for reason, count in exclusions.most_common(10)],
        )
