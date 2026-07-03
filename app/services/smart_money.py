from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from statistics import pstdev
from typing import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.models import (
    SmartMoneySignal,
    Transaction,
    Wallet,
    WalletMetric,
    WalletPosition,
    WalletScore,
)

logger = get_logger(__name__)
ZERO = Decimal("0")
HUNDRED = Decimal("100")
BUY_TYPES = ("buy", "in")
SELL_TYPES = ("sell", "out")


def clamp(value: Decimal | float, minimum: Decimal = ZERO, maximum: Decimal = HUNDRED) -> Decimal:
    return max(minimum, min(maximum, Decimal(str(value))))


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def position_return(position: WalletPosition) -> Decimal:
    invested = Decimal(position.average_entry_price or 0) * Decimal(position.total_bought_amount or 0)
    if invested <= 0:
        return ZERO
    profit = Decimal(position.realized_profit or 0) + Decimal(position.unrealized_profit or 0)
    return profit / invested * HUNDRED


class WalletAnalyzer:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    @staticmethod
    def apply_transaction(position: WalletPosition, transaction: Transaction) -> None:
        amount = Decimal(transaction.amount or 0)
        price = Decimal(transaction.price or 0)
        transaction_type = transaction.transaction_type.lower()
        if transaction_type in BUY_TYPES:
            previous_bought = Decimal(position.total_bought_amount or 0)
            if price > 0:
                previous_cost = Decimal(position.average_entry_price or 0) * previous_bought
                position.average_entry_price = (previous_cost + price * amount) / (previous_bought + amount)
            position.total_bought_amount = previous_bought + amount
            position.current_balance = Decimal(position.current_balance or 0) + amount
            position.first_purchase_date = position.first_purchase_date or transaction.timestamp
        elif transaction_type in SELL_TYPES:
            position.total_sold_amount = Decimal(position.total_sold_amount or 0) + amount
            if price > 0:
                position.realized_profit = Decimal(position.realized_profit or 0) + (
                    price - Decimal(position.average_entry_price or 0)
                ) * amount
            position.current_balance = max(ZERO, Decimal(position.current_balance or 0) - amount)
        if price > 0:
            position.unrealized_profit = Decimal(position.current_balance or 0) * (
                price - Decimal(position.average_entry_price or 0)
            )
        position.latest_activity_date = transaction.timestamp

    async def analyze_wallet(self, wallet_id: int) -> WalletMetric:
        metric = await self.session.scalar(
            select(WalletMetric).where(WalletMetric.wallet_id == wallet_id)
        )
        if metric is None:
            metric = WalletMetric(wallet_id=wallet_id, last_processed_transaction_id=0)
            self.session.add(metric)
            await self.session.flush()

        positions = list(
            (
                await self.session.scalars(
                    select(WalletPosition).where(WalletPosition.wallet_id == wallet_id)
                )
            ).all()
        )
        positions_by_token = {position.token_id: position for position in positions}
        transactions = (
            await self.session.scalars(
                select(Transaction)
                .where(
                    Transaction.wallet_id == wallet_id,
                    Transaction.id > metric.last_processed_transaction_id,
                )
                .order_by(Transaction.id)
            )
        ).all()
        for transaction in transactions:
            if transaction.token_id is not None:
                position = positions_by_token.get(transaction.token_id)
                if position is None:
                    position = WalletPosition(
                        wallet_id=wallet_id,
                        token_id=transaction.token_id,
                        total_bought_amount=ZERO,
                        total_sold_amount=ZERO,
                        current_balance=ZERO,
                        average_entry_price=ZERO,
                        realized_profit=ZERO,
                        unrealized_profit=ZERO,
                        latest_activity_date=transaction.timestamp,
                    )
                    self.session.add(position)
                    positions.append(position)
                    positions_by_token[transaction.token_id] = position
                self.apply_transaction(position, transaction)
            metric.total_transactions += 1
            if transaction.transaction_type.lower() in BUY_TYPES:
                metric.total_buys += 1
            elif transaction.transaction_type.lower() in SELL_TYPES:
                metric.total_sells += 1
            metric.last_processed_transaction_id = transaction.id

        returns = [position_return(position) for position in positions]
        profits = [
            Decimal(position.realized_profit or 0) + Decimal(position.unrealized_profit or 0)
            for position in positions
        ]
        invested = sum(
            (Decimal(position.average_entry_price or 0) * Decimal(position.total_bought_amount or 0) for position in positions),
            ZERO,
        )
        holding_days = [
            Decimal(str((aware(position.latest_activity_date) - aware(position.first_purchase_date)).total_seconds() / 86400))
            for position in positions
            if position.first_purchase_date
        ]
        metric.total_tokens_traded = len(positions)
        metric.estimated_total_profit = sum(profits, ZERO)
        metric.estimated_roi_percentage = metric.estimated_total_profit / invested * HUNDRED if invested else ZERO
        metric.average_return_percentage = sum(returns, ZERO) / len(returns) if returns else ZERO
        metric.average_holding_time_days = sum(holding_days, ZERO) / len(holding_days) if holding_days else ZERO
        metric.win_rate = Decimal(sum(value > 0 for value in profits)) / len(profits) * HUNDRED if profits else ZERO
        metric.loss_rate = Decimal(sum(value < 0 for value in profits)) / len(profits) * HUNDRED if profits else ZERO
        metric.largest_winner_percentage = max(returns, default=ZERO)
        metric.largest_loss_percentage = min(returns, default=ZERO)
        metric.last_updated = datetime.now(timezone.utc)
        await self.session.flush()
        return metric

    async def analyze_all(self) -> int:
        processed = 0
        cursor = 0
        while True:
            wallet_ids = (
                await self.session.scalars(
                    select(Wallet.id)
                    .where(Wallet.id > cursor)
                    .order_by(Wallet.id)
                    .limit(self.settings.wallet_analysis_batch_size)
                )
            ).all()
            if not wallet_ids:
                break
            for wallet_id in wallet_ids:
                await self.analyze_wallet(wallet_id)
                processed += 1
            await self.session.commit()
            cursor = wallet_ids[-1]
        logger.info("wallet_analysis_complete", wallets=processed)
        return processed


class SmartMoneyScorer:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def classify_tier(self, score: Decimal | float) -> str:
        value = Decimal(str(score))
        if value >= Decimal(str(self.settings.smart_money_elite_threshold)):
            return "ELITE"
        if value >= Decimal(str(self.settings.smart_money_advanced_threshold)):
            return "ADVANCED"
        if value >= Decimal(str(self.settings.smart_money_intermediate_threshold)):
            return "INTERMEDIATE"
        if value >= Decimal(str(self.settings.smart_money_speculative_threshold)):
            return "SPECULATIVE"
        return "LOW_QUALITY"

    @staticmethod
    def component_scores(
        metric: WalletMetric,
        positions: Iterable[WalletPosition],
        wallet_age_days: Decimal,
        now: datetime,
    ) -> dict[str, Decimal]:
        positions = list(positions)
        returns = [position_return(position) for position in positions]
        profitability = clamp(Decimal("50") + Decimal(metric.estimated_roi_percentage or 0) / 2)
        dispersion = Decimal(str(pstdev([float(value) for value in returns]))) if len(returns) > 1 else ZERO
        stability = HUNDRED / (Decimal("1") + dispersion / Decimal("25"))
        consistency = clamp(Decimal(metric.win_rate or 0) * Decimal("0.7") + stability * Decimal("0.3"))

        exposures = [
            Decimal(position.average_entry_price or 0) * Decimal(position.current_balance or 0)
            for position in positions
        ]
        total_exposure = sum(exposures, ZERO)
        concentration = max(exposures, default=ZERO) / total_exposure * HUNDRED if total_exposure else ZERO
        negative_returns = [abs(value) for value in returns if value < 0]
        average_loss = sum(negative_returns, ZERO) / len(negative_returns) if negative_returns else ZERO
        volatility_score = HUNDRED / (Decimal("1") + dispersion / Decimal("25"))
        holding_score = HUNDRED / (
            Decimal("1") + Decimal(metric.average_holding_time_days or 0) / Decimal("365")
        )
        risk_management = clamp(
            (HUNDRED - concentration) * Decimal("0.35")
            + (HUNDRED - clamp(average_loss)) * Decimal("0.30")
            + volatility_score * Decimal("0.20")
            + holding_score * Decimal("0.15")
        )

        experience = clamp(
            min(Decimal(metric.total_transactions) / Decimal("500") * Decimal("50"), Decimal("50"))
            + min(Decimal(metric.total_tokens_traded) / Decimal("50") * Decimal("30"), Decimal("30"))
            + min(wallet_age_days / Decimal("365") * Decimal("20"), Decimal("20"))
        )

        now = aware(now)
        weighted_recent: list[tuple[Decimal, Decimal]] = []
        for position, return_value in zip(positions, returns):
            age = now - aware(position.latest_activity_date)
            if age <= timedelta(days=30):
                weighted_recent.append((return_value, Decimal("2")))
            elif age <= timedelta(days=90):
                weighted_recent.append((return_value, Decimal("1")))
        if weighted_recent:
            recent_return = sum((value * weight for value, weight in weighted_recent), ZERO) / sum(
                (weight for _, weight in weighted_recent), ZERO
            )
            recent_performance = clamp(Decimal("50") + recent_return / 2)
        else:
            recent_performance = Decimal("25")
        return {
            "profitability": profitability,
            "consistency": consistency,
            "risk_management": risk_management,
            "experience": experience,
            "recent_performance": recent_performance,
        }

    def final_score(self, components: dict[str, Decimal]) -> Decimal:
        weights = self.settings.smart_money_weights
        total_weight = Decimal(str(sum(weights.values())))
        return clamp(
            sum(
                (components[name] * Decimal(str(weight)) for name, weight in weights.items()),
                ZERO,
            )
            / total_weight
        )

    @staticmethod
    def scoring_confidence(metric: WalletMetric) -> Decimal:
        return clamp(
            min(Decimal(metric.total_transactions) / Decimal("100") * Decimal("50"), Decimal("50"))
            + min(Decimal(metric.total_tokens_traded) / Decimal("20") * Decimal("30"), Decimal("30"))
            + min((Decimal(metric.win_rate or 0) + Decimal(metric.loss_rate or 0)) / HUNDRED * Decimal("20"), Decimal("20"))
        )

    async def score_wallet(self, wallet_id: int, now: datetime | None = None) -> WalletScore | None:
        metric = await self.session.scalar(select(WalletMetric).where(WalletMetric.wallet_id == wallet_id))
        wallet = await self.session.get(Wallet, wallet_id)
        if not metric or not wallet:
            return None
        positions = (
            await self.session.scalars(select(WalletPosition).where(WalletPosition.wallet_id == wallet_id))
        ).all()
        now = now or datetime.now(timezone.utc)
        age_days = Decimal(str(max(0, (aware(now) - aware(wallet.created_at)).total_seconds() / 86400)))
        components = self.component_scores(metric, positions, age_days, now)
        final = self.final_score(components)
        score = WalletScore(
            wallet_id=wallet_id,
            profitability_score=components["profitability"],
            consistency_score=components["consistency"],
            risk_management_score=components["risk_management"],
            experience_score=components["experience"],
            recent_performance_score=components["recent_performance"],
            final_smart_money_score=final,
            wallet_tier=self.classify_tier(final),
            confidence_score=self.scoring_confidence(metric),
            calculated_at=now,
        )
        self.session.add(score)
        await self.session.flush()
        return score

    async def score_all(self) -> int:
        processed = 0
        cursor = 0
        while True:
            wallet_ids = (
                await self.session.scalars(
                    select(WalletMetric.wallet_id)
                    .where(WalletMetric.wallet_id > cursor)
                    .order_by(WalletMetric.wallet_id)
                    .limit(self.settings.wallet_analysis_batch_size)
                )
            ).all()
            if not wallet_ids:
                break
            for wallet_id in wallet_ids:
                processed += int(await self.score_wallet(wallet_id) is not None)
            await self.session.commit()
            cursor = wallet_ids[-1]
        logger.info("wallet_scoring_complete", wallets=processed)
        return processed


class SmartMoneyDetector:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self._success_rates: dict[int, Decimal] = {}

    @staticmethod
    def confidence_score(
        average_wallet_quality: Decimal,
        participating_wallets: int,
        position_size_score: Decimal,
        historical_success: Decimal,
        recency_score: Decimal,
        cluster_target: int = 3,
    ) -> Decimal:
        participation = clamp(Decimal(participating_wallets) / Decimal(max(cluster_target, 1)) * HUNDRED)
        return clamp(
            clamp(average_wallet_quality) * Decimal("0.35")
            + participation * Decimal("0.20")
            + clamp(position_size_score) * Decimal("0.20")
            + clamp(historical_success) * Decimal("0.15")
            + clamp(recency_score) * Decimal("0.10")
        )

    async def _qualified_scores(self) -> dict[int, WalletScore]:
        latest_ids = select(func.max(WalletScore.id)).group_by(WalletScore.wallet_id)
        scores = (
            await self.session.scalars(
                select(WalletScore).where(
                    WalletScore.id.in_(latest_ids),
                    WalletScore.final_smart_money_score >= self.settings.smart_money_qualified_threshold,
                    WalletScore.wallet_tier.in_(("ELITE", "ADVANCED")),
                )
            )
        ).all()
        return {score.wallet_id: score for score in scores}

    async def _wallet_success(self, wallet_ids: Iterable[int]) -> Decimal:
        wallet_ids = list(wallet_ids)
        if all(wallet_id in self._success_rates for wallet_id in wallet_ids):
            values = [self._success_rates[wallet_id] for wallet_id in wallet_ids]
        else:
            values = (
                await self.session.scalars(
                    select(WalletMetric.win_rate).where(WalletMetric.wallet_id.in_(wallet_ids))
                )
            ).all()
        return sum((Decimal(value or 0) for value in values), ZERO) / len(values) if values else ZERO

    async def _store(
        self,
        signal_type: str,
        token_id: int,
        wallet_ids: list[int],
        transaction_ids: list[int],
        capital: Decimal,
        quality: Decimal,
        size_score: Decimal,
        recency_score: Decimal,
        details: dict,
    ) -> bool:
        fingerprint_source = f"{signal_type}:{token_id}:{','.join(map(str, sorted(transaction_ids)))}"
        fingerprint = hashlib.sha256(fingerprint_source.encode()).hexdigest()
        if await self.session.scalar(
            select(SmartMoneySignal.id).where(SmartMoneySignal.event_fingerprint == fingerprint)
        ):
            return False
        success = await self._wallet_success(wallet_ids)
        confidence = self.confidence_score(
            quality,
            len(set(wallet_ids)),
            size_score,
            success,
            recency_score,
            self.settings.smart_money_cluster_min_wallets,
        )
        signal = SmartMoneySignal(
            token_id=token_id,
            signal_type=signal_type,
            signal_strength=clamp(quality * Decimal("0.7") + size_score * Decimal("0.3")),
            confidence_score=confidence,
            number_of_smart_wallets=len(set(wallet_ids)),
            total_capital_moved=capital,
            supporting_data_json={
                "wallet_ids": sorted(set(wallet_ids)),
                "transaction_ids": sorted(transaction_ids),
                **details,
            },
            event_fingerprint=fingerprint,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(signal)
        return True

    async def detect(self, now: datetime | None = None) -> int:
        now = aware(now or datetime.now(timezone.utc))
        qualified = await self._qualified_scores()
        if not qualified:
            return 0
        wallet_ids = list(qualified)
        metric_rows = (
            await self.session.execute(
                select(WalletMetric.wallet_id, WalletMetric.win_rate).where(
                    WalletMetric.wallet_id.in_(wallet_ids)
                )
            )
        ).all()
        self._success_rates = {
            wallet_id: Decimal(win_rate or 0) for wallet_id, win_rate in metric_rows
        }
        monitor_cutoff = now - timedelta(minutes=self.settings.smart_money_monitor_window_minutes)
        cluster_cutoff = now - timedelta(hours=self.settings.smart_money_cluster_window_hours)
        accumulation_cutoff = now - timedelta(hours=self.settings.smart_money_accumulation_window_hours)
        oldest_cutoff = min(monitor_cutoff, cluster_cutoff, accumulation_cutoff)
        transactions = (
            await self.session.scalars(
                select(Transaction).where(
                    Transaction.wallet_id.in_(wallet_ids),
                    Transaction.token_id.is_not(None),
                    Transaction.timestamp >= oldest_cutoff,
                ).order_by(Transaction.timestamp)
            )
        ).all()
        created = 0

        recent = [transaction for transaction in transactions if aware(transaction.timestamp) >= monitor_cutoff]
        for transaction in recent:
            score = qualified[transaction.wallet_id]
            amount = Decimal(transaction.amount or 0)
            capital = amount * Decimal(transaction.price or 0)
            age_minutes = Decimal(str(max(0, (now - aware(transaction.timestamp)).total_seconds() / 60)))
            recency = clamp(HUNDRED - age_minutes / Decimal(max(self.settings.smart_money_monitor_window_minutes, 1)) * HUNDRED)
            if transaction.transaction_type.lower() in BUY_TYPES:
                prior_count = await self.session.scalar(
                    select(func.count(Transaction.id)).where(
                        Transaction.wallet_id == transaction.wallet_id,
                        Transaction.token_id == transaction.token_id,
                        Transaction.transaction_type.in_(BUY_TYPES),
                        Transaction.timestamp < transaction.timestamp,
                    )
                )
                historical_average = await self.session.scalar(
                    select(func.avg(Transaction.amount)).where(
                        Transaction.wallet_id == transaction.wallet_id,
                        Transaction.transaction_type.in_(BUY_TYPES),
                        Transaction.timestamp < transaction.timestamp,
                    )
                )
                ratio = amount / Decimal(historical_average) if historical_average else Decimal("1")
                if prior_count == 0 and ratio >= Decimal(str(self.settings.smart_money_entry_size_multiplier)):
                    created += int(await self._store(
                        "ELITE_ENTRY", transaction.token_id, [transaction.wallet_id], [transaction.id],
                        capital, Decimal(score.final_smart_money_score), clamp(ratio * Decimal("50")), recency,
                        {"position_size_ratio": str(ratio)},
                    ))
            elif transaction.transaction_type.lower() in SELL_TYPES:
                position = await self.session.scalar(
                    select(WalletPosition).where(
                        WalletPosition.wallet_id == transaction.wallet_id,
                        WalletPosition.token_id == transaction.token_id,
                    )
                )
                prior_balance = Decimal(position.current_balance or 0) + amount if position else amount
                reduction = amount / prior_balance * HUNDRED if prior_balance else ZERO
                if reduction >= Decimal(str(self.settings.smart_money_exit_percentage)):
                    created += int(await self._store(
                        "SMART_MONEY_EXIT", transaction.token_id, [transaction.wallet_id], [transaction.id],
                        capital, Decimal(score.final_smart_money_score), clamp(reduction), recency,
                        {"position_reduction_percentage": str(reduction)},
                    ))

        buys = [
            transaction for transaction in transactions
            if transaction.transaction_type.lower() in BUY_TYPES and aware(transaction.timestamp) >= cluster_cutoff
        ]
        by_token: dict[int, list[Transaction]] = defaultdict(list)
        for transaction in buys:
            by_token[transaction.token_id].append(transaction)
        for token_id, token_transactions in by_token.items():
            participants = sorted({transaction.wallet_id for transaction in token_transactions})
            if len(participants) >= self.settings.smart_money_cluster_min_wallets:
                quality = sum((Decimal(qualified[wallet_id].final_smart_money_score) for wallet_id in participants), ZERO) / len(participants)
                capital = sum((Decimal(item.amount or 0) * Decimal(item.price or 0) for item in token_transactions), ZERO)
                newest = max(aware(item.timestamp) for item in token_transactions)
                age_hours = Decimal(str(max(0, (now - newest).total_seconds() / 3600)))
                recency = clamp(HUNDRED - age_hours / Decimal(max(self.settings.smart_money_cluster_window_hours, 1)) * HUNDRED)
                created += int(await self._store(
                    "SMART_MONEY_CLUSTER", token_id, participants,
                    [item.id for item in token_transactions], capital, quality,
                    clamp(Decimal(len(participants)) / Decimal(self.settings.smart_money_cluster_min_wallets) * HUNDRED),
                    recency, {"window_hours": self.settings.smart_money_cluster_window_hours},
                ))

        accumulation_buys = [
            transaction for transaction in transactions
            if transaction.transaction_type.lower() in BUY_TYPES and aware(transaction.timestamp) >= accumulation_cutoff
        ]
        grouped: dict[tuple[int, int], list[Transaction]] = defaultdict(list)
        for transaction in accumulation_buys:
            grouped[(transaction.wallet_id, transaction.token_id)].append(transaction)
        for (wallet_id, token_id), items in grouped.items():
            position = await self.session.scalar(
                select(WalletPosition).where(
                    WalletPosition.wallet_id == wallet_id, WalletPosition.token_id == token_id
                )
            )
            recent_amount = sum((Decimal(item.amount or 0) for item in items), ZERO)
            prior_balance = max(ZERO, Decimal(position.current_balance or 0) - recent_amount) if position else ZERO
            increase = recent_amount / prior_balance * HUNDRED if prior_balance else (HUNDRED if recent_amount else ZERO)
            if prior_balance > 0 and increase >= Decimal(str(self.settings.smart_money_accumulation_percentage)):
                capital = sum((Decimal(item.amount or 0) * Decimal(item.price or 0) for item in items), ZERO)
                created += int(await self._store(
                    "ACCUMULATION", token_id, [wallet_id], [item.id for item in items], capital,
                    Decimal(qualified[wallet_id].final_smart_money_score), clamp(increase), HUNDRED,
                    {"position_increase_percentage": str(increase), "window_hours": self.settings.smart_money_accumulation_window_hours},
                ))
        await self.session.commit()
        logger.info("smart_money_detection_complete", signals=created)
        return created
