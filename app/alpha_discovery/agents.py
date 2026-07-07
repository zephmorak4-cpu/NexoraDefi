from __future__ import annotations

from app.alpha_discovery.types import AgentScore, DecisionResult, RiskScore, SmartMoneyScore, TokenLaunch
from app.core.config import Settings


class LaunchDetectorAgent:
    def __init__(self, market_data) -> None:
        self.market_data = market_data

    async def detect(self) -> list[TokenLaunch]:
        return await self.market_data.latest_solana_launches()


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


class MomentumAgent:
    def score(self, token: TokenLaunch) -> AgentScore:
        buys = token.txns.buys
        sells = max(token.txns.sells, 1)
        ratio = buys / sells
        score = 45.0
        reasons: list[str] = []
        if ratio >= 1.8:
            score += 25
            reasons.append("strong buy/sell ratio")
        else:
            reasons.append("buy/sell ratio not strong yet")
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
        else:
            reasons.append("creator holding checked/unknown")
        if token.top10_holder_percent is not None and token.top10_holder_percent > self.settings.alpha_max_top10_holder_percent:
            score -= 45
            reasons.append("top 10 holder concentration too high")
        else:
            reasons.append("top 10 holders checked/unknown")
        if token.liquidity_drop_percent is not None and token.liquidity_drop_percent < -25:
            score -= 30
            reasons.append("liquidity dropped sharply")
        if token.freeze_authority_active:
            score -= 25
            reasons.append("freeze authority active")
        if token.mint_authority_active:
            score -= 20
            reasons.append("mint authority active")
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
        elif final >= 80:
            decision = "WATCH_CLOSELY"
        elif final >= 70:
            decision = "MONITOR_ONLY"
        else:
            decision = "IGNORE"
        reasons = launch_quality.reasons + developer.reasons + smart_money.reasons + momentum.reasons + risk.reasons
        should_alert = decision == "ALPHA_ALERT" and final >= self.settings.alpha_min_final_alert_score
        return DecisionResult(round(final, 2), decision, should_alert, f"{decision} at {final:.2f}/100", reasons)
