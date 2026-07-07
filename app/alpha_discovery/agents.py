from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alpha_discovery.types import AgentScore, DecisionResult, RiskScore, SmartMoneyScore, TokenLaunch
from app.core.config import Settings
from app.models import AlphaScannedToken, CandidateHistory, CandidateWallet, TrackedWallet, WalletActivity


class LaunchDetectorAgent:
    def __init__(self, market_data) -> None:
        self.market_data = market_data

    async def detect(self, session: AsyncSession | None = None, settings: Settings | None = None) -> list[TokenLaunch]:
        tokens = self._dedupe(await self.market_data.latest_solana_launches())
        if session is None or settings is None:
            return tokens
        since = datetime.now(timezone.utc) - timedelta(minutes=settings.new_pair_lookback_minutes)
        recently_scanned = set(
            (
                await session.scalars(
                    select(AlphaScannedToken.token_address).where(AlphaScannedToken.last_seen_at >= since)
                )
            ).all()
        )
        return [token for token in tokens if token.token_address not in recently_scanned]

    @staticmethod
    def _dedupe(tokens: list[TokenLaunch]) -> list[TokenLaunch]:
        seen: set[str] = set()
        deduped: list[TokenLaunch] = []
        for token in tokens:
            if token.token_address in seen:
                continue
            seen.add(token.token_address)
            deduped.append(token)
        return deduped


class LaunchQualityAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def score(self, token: TokenLaunch) -> AgentScore:
        reasons: list[str] = []
        total_tx = token.txns.buys + token.txns.sells
        score = 50.0
        if not token.token_address:
            reasons.append("missing token address")
            return AgentScore(0, False, reasons)
        if (token.liquidity_usd or 0) < self.settings.alpha_min_liquidity_usd:
            reasons.append("liquidity too low")
        else:
            score += 15
        if token.market_cap_usd and token.market_cap_usd > self.settings.alpha_max_initial_market_cap_usd:
            reasons.append("initial market cap too high")
            score -= 20
        if total_tx < self.settings.alpha_min_tx_count:
            reasons.append("transaction count too low")
        else:
            score += 15
        if token.pair_address:
            score += 10
        else:
            reasons.append("trading pair unavailable")
        if token.symbol and token.name:
            score += 10
        else:
            reasons.append("token metadata incomplete")
        return AgentScore(max(0, min(score, 100)), not reasons, reasons or ["launch quality passed"])


class DeveloperReputationAgent:
    def score(self, token: TokenLaunch) -> AgentScore:
        if not token.creator_wallet:
            return AgentScore(50, True, ["creator reputation data incomplete; neutral score applied"])
        return AgentScore(50, True, ["creator wallet present; no adverse history available"])


class SmartMoneyAgent:
    def __init__(self, settings: Settings, smart_wallets: list[str] | None = None) -> None:
        self.settings = settings
        self.smart_wallets = smart_wallets or settings.alpha_smart_wallets

    def score(self, token: TokenLaunch) -> SmartMoneyScore:
        detected = 0
        reasons = ["smart wallet transaction stream unavailable; no detected accumulation"]
        score = 50.0
        if detected >= self.settings.alpha_smart_wallet_min_count:
            score += 20
            reasons = ["3+ smart wallets detected early"]
        return SmartMoneyScore(score=min(score, 100), passed=score >= 50, reasons=reasons, smart_wallets_detected=detected)

    async def score_token(self, session: AsyncSession, token: TokenLaunch) -> SmartMoneyScore:
        since = datetime.now(timezone.utc) - timedelta(hours=self.settings.alpha_smart_wallet_lookback_hours)
        tracked_count = await session.scalar(
            select(func.count(distinct(TrackedWallet.wallet_address)))
            .join(WalletActivity, WalletActivity.wallet_id == TrackedWallet.id)
            .where(
                TrackedWallet.chain == "solana",
                TrackedWallet.status == "active",
                TrackedWallet.reputation_score >= self.settings.candidate_promotion_reputation,
                WalletActivity.token_address == token.token_address,
                WalletActivity.timestamp >= since,
                WalletActivity.transaction_type.in_(("buy", "swap", "accumulate")),
            )
        )
        candidate_count = await session.scalar(
            select(func.count(distinct(CandidateWallet.wallet_address)))
            .join(CandidateHistory, CandidateHistory.wallet_id == CandidateWallet.id)
            .where(
                CandidateWallet.chain == "solana",
                CandidateWallet.candidate_score >= self.settings.candidate_promotion_score,
                CandidateWallet.reputation_score >= self.settings.candidate_promotion_reputation,
                CandidateHistory.token == token.token_address,
                CandidateHistory.timestamp >= since,
                CandidateHistory.action.in_(("buy", "swap", "accumulate")),
            )
        )
        configured_hits = 0
        if token.creator_wallet and token.creator_wallet in self.smart_wallets:
            configured_hits = 1
        detected = int(tracked_count or 0) + int(candidate_count or 0) + configured_hits
        if detected >= self.settings.alpha_smart_wallet_min_count:
            return SmartMoneyScore(
                100,
                True,
                [f"{detected} smart wallets accumulated this token inside {self.settings.alpha_smart_wallet_lookback_hours}h"],
                detected,
            )
        if detected > 0:
            return SmartMoneyScore(
                70,
                True,
                [f"{detected} smart wallet signal(s) found; below alpha confirmation threshold"],
                detected,
            )
        return SmartMoneyScore(
            50,
            True,
            ["no smart wallet accumulation detected yet"],
            0,
        )


class MomentumAgent:
    def score(self, token: TokenLaunch) -> AgentScore:
        txns = token.txns_5m if token.txns_5m.buys or token.txns_5m.sells else token.txns_1h if token.txns_1h.buys or token.txns_1h.sells else token.txns
        buys = txns.buys
        sells = max(txns.sells, 1)
        ratio = buys / sells
        score = 45.0
        reasons: list[str] = []
        if ratio >= 1.8:
            score += 25
            reasons.append(f"Buy/sell ratio {ratio:.2f} indicates stronger buying pressure")
        else:
            reasons.append(f"Buy/sell ratio {ratio:.2f} is not strong yet")
        if token.volume_usd_5m and token.volume_usd_1h and token.volume_usd_5m * 12 > token.volume_usd_1h * 1.5:
            score += 15
            reasons.append("5m volume is accelerating compared to 1h baseline")
        elif token.volume_usd_5m:
            reasons.append("5m volume available but not accelerating strongly")
        if token.volume_usd and token.volume_usd > 25000:
            score += 15
            reasons.append("meaningful early volume")
        if token.liquidity_usd and token.liquidity_usd >= 10000:
            score += 15
            reasons.append("liquidity above early threshold")
        return AgentScore(min(score, 100), score >= 60, reasons)


class RiskAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def score(self, token: TokenLaunch) -> RiskScore:
        score = 80.0
        reasons: list[str] = []
        if token.creator_hold_percent is not None and token.creator_hold_percent > self.settings.alpha_max_creator_hold_percent:
            score -= 45
            reasons.append("creator holding too high")
        elif token.creator_hold_percent is None:
            score -= 5
            reasons.append("Creator holder data unavailable")
        else:
            reasons.append("creator holding checked")
        if token.top10_holder_percent is not None and token.top10_holder_percent > self.settings.alpha_max_top10_holder_percent:
            score -= 45
            reasons.append("top 10 holder concentration too high")
        elif token.top10_holder_percent is None:
            score -= 5
            reasons.append("Top holder data unavailable")
        else:
            reasons.append(f"top 10 holders checked at {token.top10_holder_percent:.2f}%")
        if token.liquidity_drop_percent is not None and token.liquidity_drop_percent < -25:
            score -= 30
            reasons.append("liquidity dropped sharply")
        if token.freeze_authority_active:
            score -= 25
            reasons.append("freeze authority active")
        elif token.freeze_authority_active is None:
            score -= 3
            reasons.append("freeze authority unavailable")
        if token.mint_authority_active:
            score -= 20
            reasons.append("mint authority active")
        elif token.mint_authority_active is None:
            score -= 3
            reasons.append("mint authority unavailable")
        if token.risk_flags:
            score -= min(len(token.risk_flags) * 3, 15)
            reasons.append(f"provider risk flags present: {', '.join(token.risk_flags[:5])}")
        risk_level = "LOW" if score >= 80 else "MEDIUM" if score >= 60 else "HIGH" if score >= 35 else "EXTREME"
        return RiskScore(max(score, 0), score >= 60, reasons, risk_level)


class DecisionAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def decide(
        self,
        launch_quality: AgentScore,
        developer: AgentScore,
        smart_money: SmartMoneyScore,
        momentum: AgentScore,
        risk: RiskScore,
    ) -> DecisionResult:
        final = (
            launch_quality.score * 0.15
            + developer.score * 0.15
            + smart_money.score * 0.25
            + momentum.score * 0.25
            + risk.score * 0.20
        )
        if final >= 90:
            decision = "ALPHA_ALERT"
        elif final >= self.settings.alpha_watchlist_min_score:
            decision = "WATCH_CLOSELY"
        elif final >= 70:
            decision = "MONITOR_ONLY"
        else:
            decision = "IGNORE"
        reasons = launch_quality.reasons + developer.reasons + smart_money.reasons + momentum.reasons + risk.reasons
        should_alert = decision == "ALPHA_ALERT" and final >= self.settings.alpha_min_final_alert_score
        return DecisionResult(round(final, 2), decision, should_alert, f"{decision} at {final:.2f}/100", reasons)
