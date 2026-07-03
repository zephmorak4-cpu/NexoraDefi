from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import pstdev

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.models import (
    MomentumMetric,
    PriceHistory,
    RiskEvent,
    SmartMoneySignal,
    Token,
    TokenGrowthMetric,
    TokenRiskMetric,
    Transaction,
    WalletPosition,
)
from app.services.smart_money import HUNDRED, ZERO, aware, clamp
from app.services.token_intelligence import TokenGrowthAnalyzer, percentage_change

logger = get_logger(__name__)


class RiskAnalyzer:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def holder_distribution(self, token_id: int) -> tuple[Decimal, dict]:
        balances = list(
            (
                await self.session.scalars(
                    select(WalletPosition.current_balance)
                    .where(WalletPosition.token_id == token_id, WalletPosition.current_balance > 0)
                    .order_by(WalletPosition.current_balance.desc())
                )
            ).all()
        )
        total = sum((Decimal(value) for value in balances), ZERO)
        if total > 0:
            top10 = sum((Decimal(value) for value in balances[:10]), ZERO) / total * HUNDRED
            top20 = sum((Decimal(value) for value in balances[:20]), ZERO) / total * HUNDRED
            penalty = max(ZERO, top10 - Decimal("25")) * Decimal("1.25")
            penalty += max(ZERO, top20 - Decimal("50")) * Decimal("0.50")
            return clamp(HUNDRED - penalty), {
                "source": "wallet_positions",
                "top10_holder_percentage": str(top10),
                "top20_holder_percentage": str(top20),
                "position_count": len(balances),
            }

        growth = await self._latest_growth(token_id)
        holders = int(growth.holder_count) if growth else 0
        if holders >= 1000:
            score = Decimal("85")
        elif holders >= 100:
            score = Decimal("75")
        elif holders >= 25:
            score = Decimal("65")
        elif holders > 0:
            score = Decimal("45")
        else:
            score = Decimal("30")
        return score, {"source": "observed_holder_count", "holder_count": holders}

    async def liquidity(self, token_id: int) -> tuple[Decimal, dict]:
        growth = await self._latest_growth(token_id)
        if not growth or growth.liquidity_value is None:
            return Decimal("35"), {"source": "token_growth_metrics", "liquidity_value": None}
        base = TokenGrowthAnalyzer.liquidity_score(growth)
        decline_penalty = max(ZERO, -Decimal(growth.liquidity_growth_24h)) * Decimal("0.80")
        trend_penalty = max(ZERO, -Decimal(growth.liquidity_growth_7d)) * Decimal("0.30")
        score = clamp(base - decline_penalty - trend_penalty)
        return score, {
            "source": "token_growth_metrics",
            "liquidity_value": str(growth.liquidity_value),
            "liquidity_growth_24h": str(growth.liquidity_growth_24h),
            "liquidity_growth_7d": str(growth.liquidity_growth_7d),
        }

    async def volatility(self, token_id: int, now: datetime) -> tuple[Decimal, dict]:
        momentum = await self._latest_momentum(token_id)
        if momentum:
            movement_penalty = max(
                abs(Decimal(momentum.price_change_1h)) * Decimal("0.75"),
                abs(Decimal(momentum.price_change_24h)) * Decimal("0.40"),
            )
            score = clamp(HUNDRED - Decimal(momentum.volatility_score) - movement_penalty)
            return score, {
                "source": "momentum_metrics",
                "volatility_score": str(momentum.volatility_score),
                "price_change_1h": str(momentum.price_change_1h),
                "price_change_24h": str(momentum.price_change_24h),
            }

        prices = list(
            (
                await self.session.scalars(
                    select(PriceHistory.price)
                    .where(
                        PriceHistory.token_id == token_id,
                        PriceHistory.timestamp >= now - timedelta(days=7),
                        PriceHistory.timestamp <= now,
                    )
                    .order_by(PriceHistory.timestamp.desc())
                    .limit(1000)
                )
            ).all()
        )
        returns = [
            (float(prices[index - 1]) - float(prices[index])) / float(prices[index]) * 100
            for index in range(1, len(prices))
            if prices[index]
        ]
        volatility = clamp(Decimal(str(pstdev(returns))) * Decimal("5")) if len(returns) > 1 else ZERO
        return clamp(HUNDRED - volatility), {"source": "price_history", "volatility_score": str(volatility)}

    async def age(self, token_id: int, now: datetime) -> tuple[Decimal, dict]:
        first_activity = await self.session.scalar(
            select(func.min(Transaction.timestamp)).where(Transaction.token_id == token_id)
        )
        first_price = await self.session.scalar(
            select(func.min(PriceHistory.timestamp)).where(PriceHistory.token_id == token_id)
        )
        candidates = [aware(value) for value in (first_activity, first_price) if value is not None]
        token = await self.session.get(Token, token_id)
        if token and token.created_at:
            candidates.append(aware(token.created_at))
        if not candidates:
            return Decimal("30"), {"project_age_days": None, "source": "no_history"}
        launch = min(candidates)
        age_days = max(0, (now - launch).days)
        if age_days >= 180:
            score = Decimal("95")
        elif age_days >= 90:
            score = Decimal("85")
        elif age_days >= 30:
            score = Decimal("70")
        elif age_days >= 7:
            score = Decimal("50")
        else:
            score = Decimal("30")
        return score, {"project_age_days": age_days, "first_observed_at": launch.isoformat()}

    async def smart_money_exit(self, token_id: int, now: datetime) -> tuple[Decimal, dict]:
        signals = list(
            (
                await self.session.scalars(
                    select(SmartMoneySignal).where(
                        SmartMoneySignal.token_id == token_id,
                        SmartMoneySignal.signal_type == "SMART_MONEY_EXIT",
                        SmartMoneySignal.created_at >= now - timedelta(hours=self.settings.risk_smart_money_exit_lookback_hours),
                    )
                )
            ).all()
        )
        if not signals:
            return HUNDRED, {"exit_signal_count": 0}
        wallet_count = sum(int(signal.number_of_smart_wallets) for signal in signals)
        average_strength = sum((Decimal(signal.signal_strength) for signal in signals), ZERO) / len(signals)
        penalty = average_strength * Decimal("0.65") + min(Decimal(wallet_count) * Decimal("6"), Decimal("35"))
        return clamp(HUNDRED - penalty), {
            "exit_signal_count": len(signals),
            "smart_wallets_exiting": wallet_count,
            "average_exit_strength": str(average_strength),
            "signal_ids": [signal.id for signal in signals],
        }

    async def contract_security(self, token_id: int) -> tuple[Decimal, dict]:
        token = await self.session.get(Token, token_id)
        if not token or not token.blockchain_address:
            return Decimal("50"), {
                "contract_address": None,
                "verification_status": "unavailable",
                "dangerous_permissions_detected": False,
            }
        return Decimal("60"), {
            "contract_address": token.blockchain_address,
            "verification_status": "unknown_free_source",
            "dangerous_permissions_detected": False,
        }

    def final_score(self, components: dict[str, Decimal]) -> Decimal:
        weights = self.settings.risk_weights
        total = Decimal(str(sum(weights.values())))
        return clamp(
            (
                components["holder_distribution"] * Decimal(str(weights["holder_distribution"]))
                + components["liquidity_stability"] * Decimal(str(weights["liquidity_stability"]))
                + components["volatility"] * Decimal(str(weights["volatility"]))
                + components["project_age"] * Decimal(str(weights["project_age"]))
                + components["smart_money_behavior"] * Decimal(str(weights["smart_money_behavior"]))
                + components["contract_security"] * Decimal(str(weights["contract_security"]))
            )
            / total
        )

    def classify(self, score: Decimal) -> str:
        if score >= Decimal(str(self.settings.risk_low_threshold)):
            return "LOW"
        if score >= Decimal(str(self.settings.risk_medium_threshold)):
            return "MEDIUM"
        return "HIGH"

    async def analyze_token(self, token_id: int, now: datetime | None = None) -> TokenRiskMetric:
        now = aware(now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
        holder, holder_data = await self.holder_distribution(token_id)
        liquidity, liquidity_data = await self.liquidity(token_id)
        volatility, volatility_data = await self.volatility(token_id, now)
        age, age_data = await self.age(token_id, now)
        smart_money, smart_money_data = await self.smart_money_exit(token_id, now)
        contract, contract_data = await self.contract_security(token_id)
        components = {
            "holder_distribution": holder,
            "liquidity_stability": liquidity,
            "volatility": volatility,
            "project_age": age,
            "smart_money_behavior": smart_money,
            "contract_security": contract,
        }
        score = self.final_score(components)
        metric = TokenRiskMetric(
            token_id=token_id,
            holder_concentration_score=holder,
            liquidity_risk_score=liquidity,
            volatility_risk_score=volatility,
            age_risk_score=age,
            smart_money_exit_risk_score=smart_money,
            contract_security_score=contract,
            overall_risk_score=score,
            risk_level=self.classify(score),
            calculated_at=now,
        )
        metric._risk_factors = {
            "holder_distribution": holder_data,
            "liquidity": liquidity_data,
            "volatility": volatility_data,
            "project_age": age_data,
            "smart_money_behavior": smart_money_data,
            "contract_security": contract_data,
        }
        self.session.add(metric)
        await self.session.flush()
        return metric

    async def analyze_all(self) -> int:
        processed = 0
        cursor = 0
        now = datetime.now(timezone.utc)
        while True:
            token_ids = (
                await self.session.scalars(
                    select(Token.id).where(Token.id > cursor).order_by(Token.id).limit(self.settings.risk_batch_size)
                )
            ).all()
            if not token_ids:
                break
            for token_id in token_ids:
                await self.analyze_token(token_id, now)
                processed += 1
            await self.session.commit()
            cursor = token_ids[-1]
        logger.info("risk_analysis_complete", tokens=processed)
        return processed

    async def _latest_growth(self, token_id: int) -> TokenGrowthMetric | None:
        return await self.session.scalar(
            select(TokenGrowthMetric).where(TokenGrowthMetric.token_id == token_id).order_by(TokenGrowthMetric.id.desc()).limit(1)
        )

    async def _latest_momentum(self, token_id: int) -> MomentumMetric | None:
        return await self.session.scalar(
            select(MomentumMetric).where(MomentumMetric.token_id == token_id).order_by(MomentumMetric.id.desc()).limit(1)
        )


class RiskEventDetector:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def detect_token(self, token_id: int, now: datetime | None = None) -> list[RiskEvent]:
        now = aware(now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
        analyzer = RiskAnalyzer(self.session, self.settings)
        metric = await self.session.scalar(
            select(TokenRiskMetric).where(TokenRiskMetric.token_id == token_id).order_by(TokenRiskMetric.id.desc()).limit(1)
        )
        if metric is None:
            metric = await analyzer.analyze_token(token_id, now)
        holder_score, holder_data = await analyzer.holder_distribution(token_id)
        _, liquidity_data = await analyzer.liquidity(token_id)
        _, volatility_data = await analyzer.volatility(token_id, now)
        _, smart_money_data = await analyzer.smart_money_exit(token_id, now)
        _, contract_data = await analyzer.contract_security(token_id)

        candidates: list[tuple[str, str, Decimal, str, dict]] = []
        top10 = Decimal(str(holder_data.get("top10_holder_percentage", "0")))
        top20 = Decimal(str(holder_data.get("top20_holder_percentage", "0")))
        if top10 >= Decimal(str(self.settings.risk_top10_holder_warning_percentage)) or top20 >= Decimal(str(self.settings.risk_top20_holder_warning_percentage)) or holder_score < 40:
            candidates.append((
                "TOKEN_CONCENTRATION", "HIGH", clamp(HUNDRED - holder_score),
                "Holder distribution concentration exceeded configured risk thresholds.", holder_data,
            ))

        liquidity_growth = Decimal(str(liquidity_data.get("liquidity_growth_24h", "0") or "0"))
        if liquidity_growth <= Decimal(str(self.settings.risk_liquidity_drop_warning_percentage)) or Decimal(metric.liquidity_risk_score) < 35:
            candidates.append((
                "LIQUIDITY_WARNING", "HIGH", clamp(abs(liquidity_growth)),
                "Liquidity declined rapidly or available liquidity is insufficient.", liquidity_data,
            ))

        observed_volatility = Decimal(str(volatility_data.get("volatility_score", "0")))
        if observed_volatility >= Decimal(str(self.settings.risk_extreme_volatility_threshold)) or Decimal(metric.volatility_risk_score) < 30:
            candidates.append((
                "EXTREME_VOLATILITY", "HIGH", clamp(max(observed_volatility, HUNDRED - Decimal(metric.volatility_risk_score))),
                "Observed price movement exceeded configured volatility risk thresholds.", volatility_data,
            ))

        exiting_wallets = int(smart_money_data.get("smart_wallets_exiting", 0))
        if exiting_wallets >= self.settings.risk_smart_money_exit_wallet_threshold or Decimal(metric.smart_money_exit_risk_score) < 50:
            candidates.append((
                "SMART_MONEY_EXIT", "CRITICAL", clamp(HUNDRED - Decimal(metric.smart_money_exit_risk_score)),
                "Multiple smart money wallets reduced exposure within the monitoring window.", smart_money_data,
            ))

        if Decimal(metric.contract_security_score) < 50:
            candidates.append((
                "CONTRACT_RISK", "MEDIUM", clamp(HUNDRED - Decimal(metric.contract_security_score)),
                "Contract security source data indicates elevated permissions or verification risk.", contract_data,
            ))

        events = []
        for event_type, severity, confidence, description, data in candidates:
            existing = await self.session.scalar(
                select(RiskEvent)
                .where(
                    RiskEvent.token_id == token_id,
                    RiskEvent.event_type == event_type,
                    RiskEvent.created_at >= now - timedelta(hours=1),
                )
                .order_by(RiskEvent.id.desc())
                .limit(1)
            )
            if existing:
                continue
            event = RiskEvent(
                token_id=token_id,
                event_type=event_type,
                severity=severity,
                confidence_score=confidence,
                description=description,
                supporting_data_json=data,
                created_at=now,
            )
            self.session.add(event)
            events.append(event)
        await self.session.flush()
        return events

    async def detect_all(self) -> int:
        created = 0
        cursor = 0
        now = datetime.now(timezone.utc)
        while True:
            token_ids = (
                await self.session.scalars(
                    select(Token.id).where(Token.id > cursor).order_by(Token.id).limit(self.settings.risk_batch_size)
                )
            ).all()
            if not token_ids:
                break
            for token_id in token_ids:
                created += len(await self.detect_token(token_id, now))
            await self.session.commit()
            cursor = token_ids[-1]
        logger.info("risk_event_detection_complete", events=created)
        return created
