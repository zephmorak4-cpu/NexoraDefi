from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alpha_discovery.types import AgentScore, DecisionResult, RiskScore, SmartMoneyScore, TokenLaunch
from app.core.config import Settings
from app.models import AlphaScannedToken, CandidateHistory, CandidateWallet, TrackedWallet, WalletActivity
from app.services.smart_money import aware


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
            return AgentScore(25, False, ["creator wallet unavailable; high uncertainty"])
        return AgentScore(35, True, ["creator reputation data incomplete; cautious unknown score applied"])


class SmartMoneyAgent:
    def __init__(self, settings: Settings, smart_wallets: list[str] | None = None) -> None:
        self.settings = settings
        self.smart_wallets = smart_wallets or settings.alpha_smart_wallets

    def score(self, token: TokenLaunch) -> SmartMoneyScore:
        return SmartMoneyScore(
            20,
            False,
            ["smart wallet transaction stream unavailable; confidence capped"],
            0,
        )

    async def score_token(self, session: AsyncSession, token: TokenLaunch) -> SmartMoneyScore:
        since = datetime.now(timezone.utc) - timedelta(hours=self.settings.alpha_smart_wallet_lookback_hours)
        try:
            tracked_rows = (
                await session.execute(
                    select(distinct(TrackedWallet.wallet_address), WalletActivity.timestamp)
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
            ).all()
            candidate_rows = (
                await session.execute(
                    select(distinct(CandidateWallet.wallet_address), CandidateHistory.timestamp)
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
            ).all()
        except Exception:
            return SmartMoneyScore(
                20,
                False,
                ["smart wallet transaction stream unavailable; confidence capped"],
                0,
            )
        configured_hits = 0
        if token.creator_wallet and token.creator_wallet in self.smart_wallets:
            configured_hits = 1
        detected_wallets = {row[0] for row in tracked_rows + candidate_rows if row[0]}
        detected = len(detected_wallets) + configured_hits
        timestamps = [aware(row[1]) for row in tracked_rows + candidate_rows if row[1]]
        within_15 = False
        if len(timestamps) >= 3:
            ordered = sorted(timestamps)
            within_15 = (ordered[-1] - ordered[0]).total_seconds() <= 900
        if detected >= 3 and within_15:
            return SmartMoneyScore(
                85,
                True,
                ["3+ smart wallets detected within 15 minutes"],
                detected,
            )
        if detected >= 3:
            return SmartMoneyScore(
                75,
                True,
                [f"{detected} smart wallets detected; confirmation spread beyond 15 minutes"],
                detected,
            )
        if detected == 2:
            return SmartMoneyScore(
                60,
                True,
                ["2 smart wallets detected; moderate confirmation"],
                detected,
            )
        if detected == 1:
            return SmartMoneyScore(
                45,
                False,
                ["only 1 smart wallet detected; insufficient confirmation"],
                detected,
            )
        return SmartMoneyScore(
            30,
            False,
            ["no smart wallet accumulation detected"],
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
        token: TokenLaunch | None = None,
    ) -> DecisionResult:
        raw = (
            launch_quality.score * 0.15
            + developer.score * 0.15
            + smart_money.score * 0.25
            + momentum.score * 0.25
            + risk.score * 0.20
        )
        final = raw
        reasons = launch_quality.reasons + developer.reasons + smart_money.reasons + momentum.reasons + risk.reasons
        caps: list[str] = []
        forced_ignore = False
        if token is not None and (token.liquidity_usd or 0) < self.settings.alpha_min_liquidity_usd:
            final = min(final, 59)
            forced_ignore = True
            caps.append("liquidity below minimum; token rejected")
        if risk.risk_level == "EXTREME":
            final = min(final, 49)
            forced_ignore = True
            caps.append("extreme risk capped score at 49")
        elif risk.risk_level == "HIGH":
            final = min(final, 69)
            caps.append("high risk capped score at 69")
        if any("transaction stream unavailable" in reason for reason in smart_money.reasons):
            final = min(final, 69)
            caps.append("smart wallet stream unavailable capped score at 69")
        if any("no smart wallet accumulation detected" in reason for reason in smart_money.reasons):
            final = min(final, 74)
            caps.append("no smart money accumulation capped score at 74")
        if any("creator wallet unavailable" in reason for reason in developer.reasons):
            final = min(final, 64)
            caps.append("creator wallet missing capped score at 64")
        if any("cautious unknown score" in reason for reason in developer.reasons):
            final = min(final, 79)
            caps.append("creator reputation unknown capped score at 79")
        if any("Top holder data unavailable" in reason for reason in risk.reasons):
            final = min(final, 79)
            caps.append("holder distribution unavailable capped score at 79")
        if forced_ignore:
            decision = "IGNORE"
        elif final >= 90:
            decision = "ALPHA_ALERT"
        elif final >= 82:
            decision = "WATCH_CLOSELY"
        elif final >= 70:
            decision = "MONITOR_ONLY"
        else:
            decision = "IGNORE"
        should_alert = decision == "ALPHA_ALERT" and final >= self.settings.alpha_min_final_alert_score
        return DecisionResult(round(final, 2), decision, should_alert, f"{decision} at {final:.2f}/100", reasons + caps, round(raw, 2), caps)
