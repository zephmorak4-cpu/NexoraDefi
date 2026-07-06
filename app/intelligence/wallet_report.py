from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.wallet_history import WalletHistoryService
from app.models import CandidateHistory, CandidateWallet, WalletReview
from app.pipeline.pipeline_state import PipelineStage, stage_at_least
from app.services.smart_money import aware, clamp


@dataclass(frozen=True)
class WalletIntelligenceReport:
    wallet_id: int
    wallet_address: str
    chain: str
    current_status: str
    wallet_type: str
    wallet_age_days: Decimal
    current_portfolio_value: Decimal
    total_trades: int
    average_trades_per_day: Decimal
    average_trades_per_week: Decimal
    average_trades_per_month: Decimal
    average_buy_size: Decimal
    average_sell_size: Decimal
    largest_buy: Decimal
    largest_sell: Decimal
    average_holding_time_days: Decimal
    median_holding_time_days: Decimal
    longest_hold_days: Decimal
    shortest_hold_days: Decimal
    held_less_than_24h_percentage: Decimal
    held_more_than_30d_percentage: Decimal
    trading_style: str
    trading_style_explanation: str
    copy_performance_score: Decimal
    wallet_reputation_score: Decimal
    historical_accuracy: Decimal
    average_roi: Decimal
    median_roi: Decimal
    total_roi: Decimal
    maximum_drawdown: Decimal
    profit_factor: Decimal
    sharpe_ratio: Decimal
    consistency: Decimal
    conviction_score: Decimal
    risk_score: Decimal
    risk_classification: str
    token_preferences: dict[str, object]
    executive_summary: str
    administrator_recommendation: str
    recommendation_reasoning: str
    review_status: str
    approved_for_signals: bool


class WalletReportEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def report_for_wallet(self, wallet_id: int) -> WalletIntelligenceReport:
        wallet = await self.session.get(CandidateWallet, wallet_id)
        if wallet is None:
            raise ValueError("candidate wallet not found")
        if not stage_at_least(wallet.pipeline_stage, PipelineStage.RANKED):
            raise ValueError("insufficient historical data: wallet has not completed the intelligence pipeline")
        history = await WalletHistoryService(self.session).for_candidate(wallet_id, limit=1000)
        review = await self._review(wallet_id)
        return self._build(wallet, history, review)

    async def reports(self) -> list[WalletIntelligenceReport]:
        wallets = list(
            (
                await self.session.scalars(
                    select(CandidateWallet)
                    .where(CandidateWallet.pipeline_stage.in_((PipelineStage.RANKED.value, PipelineStage.REPORT_GENERATED.value)))
                    .order_by(CandidateWallet.candidate_score.desc(), CandidateWallet.id)
                )
            ).all()
        )
        return [await self.report_for_wallet(wallet.id) for wallet in wallets]

    async def _review(self, wallet_id: int) -> WalletReview | None:
        return await self.session.scalar(select(WalletReview).where(WalletReview.wallet_id == wallet_id))

    def _build(
        self,
        wallet: CandidateWallet,
        history: list[CandidateHistory],
        review: WalletReview | None,
    ) -> WalletIntelligenceReport:
        now = datetime.now(tz=aware(wallet.first_seen).tzinfo)
        first_seen = aware(wallet.first_seen)
        last_seen = aware(wallet.last_seen)
        wallet_age_days = Decimal(max((now - first_seen).days, 0))
        total_trades = len(history)
        active_days = Decimal(max((last_seen.date() - first_seen.date()).days + 1, 1))
        buys = [Decimal(item.usd_value or 0) for item in history if item.action.lower() in {"buy", "swap", "accumulate"}]
        sells = [Decimal(item.usd_value or 0) for item in history if item.action.lower() in {"sell", "out"}]
        sizes = [Decimal(item.usd_value or 0) for item in history]
        holding_days = self._holding_days(history)
        roi_values = self._roi_values(history)
        average_roi = self._avg(roi_values)
        median_roi = Decimal(str(median(roi_values))) if roi_values else Decimal("0")
        total_roi = sum(roi_values, Decimal("0"))
        risk_score = self._risk_score(wallet, history)
        copy_score = self._copy_performance_score(wallet, average_roi, risk_score, total_trades)
        conviction = self._conviction_score(wallet, history)
        trading_style, style_reason = self._trading_style(wallet, history)
        recommendation, reasoning = self._recommendation(copy_score, Decimal(wallet.reputation_score), Decimal(wallet.historical_accuracy_score), risk_score, total_trades)
        return WalletIntelligenceReport(
            wallet_id=wallet.id,
            wallet_address=wallet.wallet_address,
            chain=wallet.chain,
            current_status=wallet.status,
            wallet_type=wallet.wallet_type,
            wallet_age_days=wallet_age_days,
            current_portfolio_value=sum(sizes, Decimal("0")),
            total_trades=total_trades,
            average_trades_per_day=Decimal(total_trades) / active_days,
            average_trades_per_week=Decimal(total_trades) / active_days * Decimal("7"),
            average_trades_per_month=Decimal(total_trades) / active_days * Decimal("30"),
            average_buy_size=self._avg(buys),
            average_sell_size=self._avg(sells),
            largest_buy=max(buys, default=Decimal("0")),
            largest_sell=max(sells, default=Decimal("0")),
            average_holding_time_days=self._avg(holding_days),
            median_holding_time_days=Decimal(str(median(holding_days))) if holding_days else Decimal("0"),
            longest_hold_days=max(holding_days, default=Decimal("0")),
            shortest_hold_days=min(holding_days, default=Decimal("0")),
            held_less_than_24h_percentage=self._percentage([value < 1 for value in holding_days]),
            held_more_than_30d_percentage=self._percentage([value > 30 for value in holding_days]),
            trading_style=trading_style,
            trading_style_explanation=style_reason,
            copy_performance_score=copy_score,
            wallet_reputation_score=Decimal(wallet.reputation_score),
            historical_accuracy=Decimal(wallet.historical_accuracy_score),
            average_roi=average_roi,
            median_roi=median_roi,
            total_roi=total_roi,
            maximum_drawdown=self._maximum_drawdown(roi_values),
            profit_factor=self._profit_factor(roi_values),
            sharpe_ratio=self._sharpe_ratio(roi_values),
            consistency=Decimal(wallet.candidate_score),
            conviction_score=conviction,
            risk_score=risk_score,
            risk_classification=self._risk_classification(risk_score),
            token_preferences=self._token_preferences(history),
            executive_summary=self._executive_summary(wallet, copy_score, risk_score, total_trades),
            administrator_recommendation=recommendation,
            recommendation_reasoning=reasoning,
            review_status=review.review_status if review else "Pending",
            approved_for_signals=bool(review.approved_for_signals) if review else False,
        )

    @staticmethod
    def _avg(values: list[Decimal]) -> Decimal:
        return sum(values, Decimal("0")) / Decimal(len(values)) if values else Decimal("0")

    @staticmethod
    def _percentage(flags: list[bool]) -> Decimal:
        return Decimal(sum(1 for item in flags if item)) / Decimal(len(flags)) * Decimal("100") if flags else Decimal("0")

    @staticmethod
    def _holding_days(history: list[CandidateHistory]) -> list[Decimal]:
        by_token: dict[str, list[CandidateHistory]] = {}
        for item in history:
            by_token.setdefault(item.token, []).append(item)
        holds: list[Decimal] = []
        for rows in by_token.values():
            ordered = sorted(rows, key=lambda row: aware(row.timestamp))
            if len(ordered) >= 2:
                holds.append(Decimal(str((aware(ordered[-1].timestamp) - aware(ordered[0].timestamp)).total_seconds() / 86400)))
        return holds

    @staticmethod
    def _roi_values(history: list[CandidateHistory]) -> list[Decimal]:
        values = [Decimal(item.usd_value or 0) for item in history if item.usd_value is not None]
        if not values:
            return []
        baseline = max(values[0], Decimal("1"))
        return [(value - baseline) / baseline * Decimal("100") for value in values]

    @staticmethod
    def _maximum_drawdown(roi_values: list[Decimal]) -> Decimal:
        peak = Decimal("0")
        drawdown = Decimal("0")
        running = Decimal("0")
        for value in roi_values:
            running += value
            peak = max(peak, running)
            drawdown = min(drawdown, running - peak)
        return abs(drawdown)

    @staticmethod
    def _profit_factor(roi_values: list[Decimal]) -> Decimal:
        gains = sum((value for value in roi_values if value > 0), Decimal("0"))
        losses = abs(sum((value for value in roi_values if value < 0), Decimal("0")))
        return gains / losses if losses > 0 else gains

    @staticmethod
    def _sharpe_ratio(roi_values: list[Decimal]) -> Decimal:
        if len(roi_values) < 2:
            return Decimal("0")
        avg = sum(roi_values, Decimal("0")) / Decimal(len(roi_values))
        variance = sum((value - avg) ** 2 for value in roi_values) / Decimal(len(roi_values) - 1)
        stddev = Decimal(str(float(variance) ** 0.5))
        return avg / stddev if stddev else Decimal("0")

    @staticmethod
    def _risk_score(wallet: CandidateWallet, history: list[CandidateHistory]) -> Decimal:
        activity_penalty = Decimal("30") if len(history) < 3 else Decimal("0")
        suspicious = Decimal(wallet.suspicious_score)
        return clamp(Decimal("100") - suspicious - activity_penalty)

    @staticmethod
    def _copy_performance_score(wallet: CandidateWallet, average_roi: Decimal, risk_score: Decimal, total_trades: int) -> Decimal:
        return clamp(
            Decimal(wallet.candidate_score) * Decimal("0.35")
            + Decimal(wallet.reputation_score) * Decimal("0.30")
            + Decimal(wallet.historical_accuracy_score) * Decimal("0.20")
            + risk_score * Decimal("0.10")
            + clamp(Decimal(total_trades) * Decimal("5")) * Decimal("0.05")
            + clamp(average_roi) * Decimal("0.05")
        )

    @staticmethod
    def _conviction_score(wallet: CandidateWallet, history: list[CandidateHistory]) -> Decimal:
        repeat_tokens = Counter(item.token for item in history)
        repeats = sum(1 for count in repeat_tokens.values() if count > 1)
        return clamp(Decimal(wallet.candidate_score) * Decimal("0.5") + Decimal(repeats) * Decimal("15") + Decimal(len(history)) * Decimal("3"))

    @staticmethod
    def _trading_style(wallet: CandidateWallet, history: list[CandidateHistory]) -> tuple[str, str]:
        actions = Counter(item.action.lower() for item in history)
        if wallet.wallet_type != "Unknown":
            return wallet.wallet_type, f"Discovery classifier labelled this wallet as {wallet.wallet_type} based on observed activity patterns."
        if len(history) >= 20:
            return "High Frequency Trader", "The wallet has a high number of observed trades in the candidate history."
        if actions["liquidity_add"] > 0:
            return "Liquidity Provider", "The wallet has liquidity-add activity in the observation history."
        if actions["swap"] >= max(1, len(history) // 2):
            return "Momentum Trader", "The wallet primarily appears in swap activity around trending tokens."
        return "Unknown", "There is not enough history to classify the wallet with confidence."

    @staticmethod
    def _risk_classification(risk_score: Decimal) -> str:
        if risk_score >= 80:
            return "Low Risk"
        if risk_score >= 60:
            return "Moderate Risk"
        if risk_score >= 40:
            return "High Risk"
        return "Very High Risk"

    @staticmethod
    def _token_preferences(history: list[CandidateHistory]) -> dict[str, object]:
        token_counts = Counter(item.token for item in history)
        action_counts = Counter(item.action for item in history)
        return {
            "most_traded_tokens": token_counts.most_common(10),
            "most_traded_sectors": ["Solana trending tokens"] if history else [],
            "winning_projects": [],
            "losing_projects": [],
            "preferred_holding_duration": "unknown",
            "actions": action_counts.most_common(),
        }

    @staticmethod
    def _executive_summary(wallet: CandidateWallet, copy_score: Decimal, risk_score: Decimal, total_trades: int) -> str:
        return (
            f"Wallet {wallet.wallet_address} is under manual review with {total_trades} observed events. "
            f"The current copy performance score is {copy_score:.2f}, with risk score {risk_score:.2f}. "
            "This report is for administrator review only and does not approve the wallet for signals."
        )

    @staticmethod
    def _recommendation(copy_score: Decimal, reputation: Decimal, accuracy: Decimal, risk_score: Decimal, total_trades: int) -> tuple[str, str]:
        if total_trades < 5:
            return "Needs More Observation", "The wallet has too little observed history for a confident elite decision."
        if copy_score >= 85 and reputation >= 85 and accuracy >= 75 and risk_score >= 70:
            return "Strong Elite Candidate", "Performance, reputation, accuracy, and risk profile all meet strong review standards."
        if copy_score >= 65 and reputation >= 60:
            return "Promising Candidate", "The wallet has useful signals but needs administrator review before approval."
        if risk_score < 40:
            return "Reject", "The wallet has a high-risk profile relative to the current observation data."
        return "Needs More Observation", "The wallet has not yet shown enough quality or consistency for elite status."
