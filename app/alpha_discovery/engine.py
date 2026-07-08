from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alpha_discovery.agents import (
    DecisionAgent,
    DeveloperReputationAgent,
    LaunchDetectorAgent,
    LaunchQualityAgent,
    MomentumAgent,
    RiskAgent,
    SmartMoneyAgent,
)
from app.alpha_discovery.format_alert import format_alpha_alert
from app.alpha_discovery.services import DiscordAlphaService, MarketDataService, OpenAIAlphaService, TelegramAlphaService
from app.alpha_discovery.types import AgentScore, DecisionResult, RiskScore, SmartMoneyScore, TokenLaunch
from app.core.config import Settings
from app.core.logging import get_logger
from app.models import AlphaAlertHistory, AlphaProviderSnapshot, AlphaScannedToken, AlphaWatchlistToken

logger = get_logger(__name__)


class SolanaAlphaDiscoveryEngine:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        market_data: MarketDataService | None = None,
        telegram: TelegramAlphaService | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.market_data = market_data or MarketDataService(settings)
        self.telegram = telegram or TelegramAlphaService(settings)
        self.discord = DiscordAlphaService(settings)
        self.openai = OpenAIAlphaService(settings)
        self.detector = LaunchDetectorAgent(self.market_data)
        self.launch_quality = LaunchQualityAgent(settings)
        self.developer = DeveloperReputationAgent()
        self.smart_money = SmartMoneyAgent(settings)
        self.momentum = MomentumAgent()
        self.risk = RiskAgent(settings)
        self.decision = DecisionAgent(settings)
        self.scan_id: str | None = None

    async def scan(self) -> dict[str, int]:
        self.scan_id = uuid4().hex
        tokens = await self.detector.detect(self.session, self.settings)
        logger.info("alpha_launch_detector_complete", count=len(tokens))
        counts = {"scanned": 0, "alerts": 0, "watchlist": 0, "rejected": 0}
        for token in tokens:
            try:
                result = await self._evaluate(token)
            except Exception as exc:
                logger.exception("alpha_token_scan_failed", token=token.token_address, error=type(exc).__name__)
                continue
            counts["scanned"] += 1
            if result.should_alert:
                counts["alerts"] += 1
            elif result.decision in {"WATCH_CLOSELY", "MONITOR_ONLY"}:
                counts["watchlist"] += 1
            else:
                counts["rejected"] += 1
        await self.session.commit()
        return counts

    async def _evaluate(self, token: TokenLaunch) -> DecisionResult:
        launch_quality = self.launch_quality.score(token)
        developer = self.developer.score(token)
        smart_money = await self.smart_money.score_token(self.session, token)
        momentum = self.momentum.score(token)
        risk = self.risk.score(token)
        decision = self.decision.decide(launch_quality, developer, smart_money, momentum, risk, token)
        if self.settings.debug_alpha_engine:
            logger.info(
                "alpha_debug_score_breakdown",
                token=token.token_address,
                launch_quality=launch_quality.score,
                developer=developer.score,
                smart_money=smart_money.score,
                momentum=momentum.score,
                risk=risk.score,
                raw_weighted_score=decision.raw_score,
                caps_applied=decision.caps_applied,
                final=decision.final_score,
                decision=decision.decision,
            )
        await self._persist(token, launch_quality, developer, smart_money, momentum, risk, decision)
        if decision.should_alert:
            message = format_alpha_alert(token, decision, risk, smart_money)
            sent = await self.telegram.send(message)
            await self.discord.send(message)
            if sent:
                self.session.add(
                    AlphaAlertHistory(
                        scan_id=self.scan_id,
                        token_address=token.token_address,
                        decision=decision.decision,
                        final_score=Decimal(str(decision.final_score)),
                        channel="telegram",
                        message=message,
                    )
                )
                logger.info("alpha_telegram_alert_sent", token=token.token_address, score=decision.final_score)
        elif decision.decision in {"WATCH_CLOSELY", "MONITOR_ONLY"}:
            await self._watchlist(token, decision)
        else:
            logger.info("alpha_token_rejected", token=token.token_address, reasons=decision.reasons[:5])
        return decision

    async def _persist(
        self,
        token: TokenLaunch,
        launch_quality: AgentScore,
        developer: AgentScore,
        smart_money: SmartMoneyScore,
        momentum: AgentScore,
        risk: RiskScore,
        decision: DecisionResult,
    ) -> None:
        row = await self.session.scalar(
            select(AlphaScannedToken).where(
                AlphaScannedToken.token_address == token.token_address,
                AlphaScannedToken.pair_address == token.pair_address,
            )
        )
        if row is None:
            row = AlphaScannedToken(token_address=token.token_address, pair_address=token.pair_address)
        row.scan_id = self.scan_id
        row.symbol = token.symbol
        row.name = token.name
        row.creator_wallet = token.creator_wallet
        row.launch_time = token.launch_time
        row.dex = token.dex
        row.source = token.source
        row.liquidity_usd = Decimal(str(token.liquidity_usd)) if token.liquidity_usd is not None else None
        row.market_cap_usd = Decimal(str(token.market_cap_usd)) if token.market_cap_usd is not None else None
        row.price_usd = Decimal(str(token.price_usd)) if token.price_usd is not None else None
        row.volume_usd = Decimal(str(token.volume_usd)) if token.volume_usd is not None else None
        row.buys = token.txns.buys
        row.sells = token.txns.sells
        row.final_score = Decimal(str(decision.final_score))
        row.decision = decision.decision
        row.should_alert = decision.should_alert
        row.rejection_reasons = decision.reasons
        row.agent_scores = {
            "launch_quality": launch_quality.score,
            "developer_reputation": developer.score,
            "smart_money": smart_money.score,
            "momentum": momentum.score,
            "risk": risk.score,
        }
        self.session.add(row)
        for snapshot in token.provider_snapshots:
            self.session.add(
                AlphaProviderSnapshot(
                    scan_id=self.scan_id,
                    token_address=token.token_address,
                    pair_address=token.pair_address,
                    provider=snapshot.provider,
                    raw_response_json=snapshot.raw_response,
                    normalized_data_json=snapshot.normalized_data,
                )
            )

    async def _watchlist(self, token: TokenLaunch, decision: DecisionResult) -> None:
        row = await self.session.scalar(
            select(AlphaWatchlistToken).where(AlphaWatchlistToken.token_address == token.token_address)
        )
        if row is None:
            row = AlphaWatchlistToken(token_address=token.token_address)
        row.decision = decision.decision
        row.final_score = Decimal(str(decision.final_score))
        row.reasons = decision.reasons
        self.session.add(row)

    async def close(self) -> None:
        await self.market_data.close()
        await self.telegram.close()
