from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    PaperAccount,
    PaperPosition,
    SpotCandle,
    SpotSetupEvaluation,
    SpotToken,
    SpotTradeSignal,
    SpotUniverseMember,
    SpotUniverseSnapshot,
)
from app.spot.types import Candle, PaperTradeState, SetupEvaluationResult, TokenAsset, TradePlan
from app.spot.universe import UniverseBuild


def dec(value: float | int | None) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


class SpotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_universe(self, build: UniverseBuild) -> None:
        self.session.add(
            SpotUniverseSnapshot(
                snapshot_id=build.snapshot_id,
                candidates_discovered=build.raw_candidates_retrieved,
                eligible_count=len(build.eligible),
                core_count=len(build.core),
                candidate_count=len(build.candidate),
                excluded_count=len(build.excluded),
                exclusion_summary=build.exclusion_summary,
            )
        )
        for member in [*build.core, *build.candidate, *build.excluded]:
            token = member.token
            row = await self.session.scalar(select(SpotToken).where(SpotToken.address == token.address))
            if row is None:
                row = SpotToken(address=token.address, symbol=token.symbol, name=token.name)
            row.chain = token.chain
            row.symbol = token.symbol
            row.name = token.name
            row.decimals = token.decimals
            row.created_at = token.created_at
            row.market_cap_usd = dec(token.market_cap_usd)
            row.fdv_usd = dec(token.fdv_usd)
            row.liquidity_usd = dec(token.liquidity_usd)
            row.volume_24h_usd = dec(token.volume_24h_usd)
            row.primary_pool_address = token.primary_pool_address
            row.primary_dex = token.primary_dex
            row.quote_asset = token.quote_asset
            row.data_sources = token.data_sources
            self.session.add(row)
            self.session.add(
                SpotUniverseMember(
                    snapshot_id=build.snapshot_id,
                    token_address=token.address,
                    tier=member.tier,
                    rank=member.rank,
                    score=dec(member.score) or Decimal("0"),
                    reasons=member.reasons,
                    factors=member.factors,
                )
            )

    async def latest_core_tokens(self) -> list[TokenAsset]:
        snapshot_id = await self.session.scalar(
            select(SpotUniverseSnapshot.snapshot_id).order_by(desc(SpotUniverseSnapshot.created_at)).limit(1)
        )
        if not snapshot_id:
            return []
        rows = (
            await self.session.execute(
                select(SpotToken)
                .join(SpotUniverseMember, SpotUniverseMember.token_address == SpotToken.address)
                .where(SpotUniverseMember.snapshot_id == snapshot_id, SpotUniverseMember.tier == "CORE")
                .order_by(SpotUniverseMember.rank)
            )
        ).scalars().all()
        return [
            TokenAsset(
                chain=row.chain,
                address=row.address,
                symbol=row.symbol,
                name=row.name,
                decimals=row.decimals,
                created_at=row.created_at,
                market_cap_usd=float(row.market_cap_usd) if row.market_cap_usd is not None else None,
                fdv_usd=float(row.fdv_usd) if row.fdv_usd is not None else None,
                liquidity_usd=float(row.liquidity_usd) if row.liquidity_usd is not None else None,
                volume_24h_usd=float(row.volume_24h_usd) if row.volume_24h_usd is not None else None,
                primary_pool_address=row.primary_pool_address,
                primary_dex=row.primary_dex,
                quote_asset=row.quote_asset,
                data_sources=row.data_sources or [],
            )
            for row in rows
        ]

    async def latest_universe_members(self, tier: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        snapshot_id = await self.session.scalar(
            select(SpotUniverseSnapshot.snapshot_id).order_by(desc(SpotUniverseSnapshot.created_at)).limit(1)
        )
        if not snapshot_id:
            return []
        query = (
            select(SpotUniverseMember, SpotToken)
            .join(SpotToken, SpotToken.address == SpotUniverseMember.token_address)
            .where(SpotUniverseMember.snapshot_id == snapshot_id)
            .order_by(SpotUniverseMember.tier, SpotUniverseMember.rank)
            .limit(limit)
        )
        if tier:
            query = query.where(SpotUniverseMember.tier == tier.upper())
        rows = (await self.session.execute(query)).all()
        return [
            {
                "tier": member.tier,
                "rank": member.rank,
                "symbol": token.symbol,
                "address": token.address,
                "pool": token.primary_pool_address,
                "score": float(member.score),
                "liquidity_usd": float(token.liquidity_usd) if token.liquidity_usd is not None else None,
                "volume_24h_usd": float(token.volume_24h_usd) if token.volume_24h_usd is not None else None,
                "reasons": member.reasons,
                "factors": member.factors,
            }
            for member, token in rows
        ]

    async def latest_token(self, token_address: str) -> TokenAsset | None:
        row = await self.session.scalar(select(SpotToken).where(SpotToken.address == token_address))
        if row is None:
            return None
        return TokenAsset(
            chain=row.chain,
            address=row.address,
            symbol=row.symbol,
            name=row.name,
            decimals=row.decimals,
            created_at=row.created_at,
            market_cap_usd=float(row.market_cap_usd) if row.market_cap_usd is not None else None,
            fdv_usd=float(row.fdv_usd) if row.fdv_usd is not None else None,
            liquidity_usd=float(row.liquidity_usd) if row.liquidity_usd is not None else None,
            volume_24h_usd=float(row.volume_24h_usd) if row.volume_24h_usd is not None else None,
            primary_pool_address=row.primary_pool_address,
            primary_dex=row.primary_dex,
            quote_asset=row.quote_asset,
            data_sources=row.data_sources or [],
        )

    async def upsert_candles(self, candles: Iterable[Candle]) -> None:
        for candle in candles:
            existing = await self.session.scalar(
                select(SpotCandle).where(
                    SpotCandle.token_address == candle.token_address,
                    SpotCandle.pool_address == candle.pool_address,
                    SpotCandle.timeframe == candle.timeframe,
                    SpotCandle.timestamp == candle.timestamp,
                    SpotCandle.source == candle.source,
                )
            )
            row = existing or SpotCandle(
                token_address=candle.token_address,
                pool_address=candle.pool_address,
                timeframe=candle.timeframe,
                timestamp=candle.timestamp,
                source=candle.source,
            )
            row.open = dec(candle.open) or Decimal("0")
            row.high = dec(candle.high) or Decimal("0")
            row.low = dec(candle.low) or Decimal("0")
            row.close = dec(candle.close) or Decimal("0")
            row.volume = dec(candle.volume) or Decimal("0")
            row.is_closed = candle.is_closed
            self.session.add(row)

    async def candles(self, token_address: str, timeframe: str, limit: int) -> list[Candle]:
        rows = (
            await self.session.scalars(
                select(SpotCandle)
                .where(SpotCandle.token_address == token_address, SpotCandle.timeframe == timeframe)
                .order_by(desc(SpotCandle.timestamp))
                .limit(limit)
            )
        ).all()
        by_timestamp = {}
        source_rank = {"GeckoTerminal": 2, "Birdeye": 1}
        for row in rows:
            current = by_timestamp.get(row.timestamp)
            if current is None or source_rank.get(row.source, 0) > source_rank.get(current.source, 0):
                by_timestamp[row.timestamp] = row
        deduped = sorted(by_timestamp.values(), key=lambda row: row.timestamp)[-limit:]
        return [
            Candle(
                token_address=row.token_address,
                pool_address=row.pool_address,
                timeframe=row.timeframe,
                timestamp=row.timestamp,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
                source=row.source,
                is_closed=row.is_closed,
            )
            for row in deduped
        ]

    async def signal_exists(self, fingerprint: str) -> bool:
        return bool(await self.session.scalar(select(SpotTradeSignal.id).where(SpotTradeSignal.fingerprint == fingerprint)))

    async def save_evaluation(self, scan_id: str, result: SetupEvaluationResult, strategy_version: str) -> None:
        self.session.add(
            SpotSetupEvaluation(
                scan_id=scan_id,
                token_address=result.token.address,
                strategy_version=strategy_version,
                decision=result.decision.value,
                quality_score=dec(result.quality_score) or Decimal("0"),
                reward_risk=dec(result.reward_risk),
                rejection_reasons=result.reasons,
                plan_json=plan_to_json(result.plan) if result.plan else None,
            )
        )

    async def save_signal(self, plan: TradePlan) -> None:
        self.session.add(
            SpotTradeSignal(
                fingerprint=plan.fingerprint,
                token_address=plan.token.address,
                strategy_version=plan.strategy_version,
                quality_score=dec(plan.quality_score) or Decimal("0"),
                reward_risk=dec(plan.reward_risk) or Decimal("0"),
                plan_json=plan_to_json(plan),
            )
        )

    async def default_account(self, starting_balance: float) -> PaperAccount:
        row = await self.session.scalar(select(PaperAccount).where(PaperAccount.name == "default"))
        if row is None:
            row = PaperAccount(
                name="default",
                starting_balance_usd=dec(starting_balance) or Decimal("0"),
                cash_balance_usd=dec(starting_balance) or Decimal("0"),
                equity_usd=dec(starting_balance) or Decimal("0"),
            )
            self.session.add(row)
        return row

    async def open_positions_count(self) -> int:
        rows = await self.session.scalars(
            select(PaperPosition).where(PaperPosition.state.in_([PaperTradeState.WAITING_FOR_ENTRY.value, PaperTradeState.OPEN.value]))
        )
        return len(rows.all())

    async def recent_signals(self, limit: int = 20) -> list[dict[str, object]]:
        rows = (
            await self.session.scalars(select(SpotTradeSignal).order_by(desc(SpotTradeSignal.created_at)).limit(limit))
        ).all()
        return [
            {
                "created_at": row.created_at,
                "token_address": row.token_address,
                "quality_score": float(row.quality_score),
                "reward_risk": float(row.reward_risk),
                "fingerprint": row.fingerprint,
                "notification_status": row.notification_status,
                "plan": row.plan_json,
            }
            for row in rows
        ]

    async def paper_positions(self, state: str | None = None, limit: int = 50) -> list[dict[str, object]]:
        query = select(PaperPosition).order_by(desc(PaperPosition.created_at)).limit(limit)
        if state:
            query = query.where(PaperPosition.state == state)
        rows = (await self.session.scalars(query)).all()
        return [
            {
                "id": row.id,
                "state": row.state,
                "token_address": row.token_address,
                "signal_fingerprint": row.signal_fingerprint,
                "entry_price": float(row.entry_price) if row.entry_price is not None else None,
                "stop_loss": float(row.stop_loss),
                "targets": [float(row.target_1), float(row.target_2), float(row.target_3)],
                "quantity": float(row.quantity) if row.quantity is not None else None,
                "realized_pnl_usd": float(row.realized_pnl_usd),
                "opened_at": row.opened_at,
                "closed_at": row.closed_at,
            }
            for row in rows
        ]

    async def paper_trade_summary(self) -> dict[str, object]:
        rows = (await self.session.scalars(select(PaperPosition))).all()
        closed = [row for row in rows if row.state.startswith("CLOSED")]
        wins = [row for row in closed if float(row.realized_pnl_usd) > 0]
        losses = [row for row in closed if float(row.realized_pnl_usd) <= 0]
        gross_wins = sum(float(row.realized_pnl_usd) for row in wins)
        gross_losses = abs(sum(float(row.realized_pnl_usd) for row in losses))
        return {
            "positions_total": len(rows),
            "open_or_waiting": sum(row.state in {PaperTradeState.WAITING_FOR_ENTRY.value, PaperTradeState.OPEN.value} for row in rows),
            "completed_trades": len(closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (len(wins) / len(closed)) if closed else 0,
            "net_pnl_usd": sum(float(row.realized_pnl_usd) for row in closed),
            "profit_factor": (gross_wins / gross_losses) if gross_losses else None,
        }

    async def latest_scan_funnel(self) -> dict[str, object]:
        scan_id = await self.session.scalar(
            select(SpotSetupEvaluation.scan_id).order_by(desc(SpotSetupEvaluation.created_at)).limit(1)
        )
        if not scan_id:
            return {"scan_id": None, "tokens_evaluated": 0, "signals": 0, "rejection_reasons": []}
        rows = (
            await self.session.scalars(select(SpotSetupEvaluation).where(SpotSetupEvaluation.scan_id == scan_id))
        ).all()
        reasons: dict[str, int] = {}
        for row in rows:
            for reason in row.rejection_reasons or []:
                reasons[reason] = reasons.get(reason, 0) + 1
        signals = await self.session.scalar(
            select(func.count(SpotTradeSignal.id)).where(SpotTradeSignal.created_at >= min(row.created_at for row in rows))
        )
        return {
            "scan_id": scan_id,
            "tokens_evaluated": len(rows),
            "signals": int(signals or 0),
            "rejection_reasons": [{"reason": reason, "count": count} for reason, count in sorted(reasons.items(), key=lambda item: item[1], reverse=True)[:10]],
        }

    async def latest_scan_evaluations(self, limit: int = 100) -> dict[str, object]:
        scan_id = await self.session.scalar(
            select(SpotSetupEvaluation.scan_id).order_by(desc(SpotSetupEvaluation.created_at)).limit(1)
        )
        if not scan_id:
            return {"scan_id": None, "evaluations": []}
        rows = (
            await self.session.execute(
                select(SpotSetupEvaluation, SpotToken)
                .join(SpotToken, SpotToken.address == SpotSetupEvaluation.token_address)
                .where(SpotSetupEvaluation.scan_id == scan_id)
                .order_by(SpotToken.symbol)
                .limit(limit)
            )
        ).all()
        return {
            "scan_id": scan_id,
            "evaluations": [
                {
                    "symbol": token.symbol,
                    "address": token.address,
                    "decision": evaluation.decision,
                    "quality_score": float(evaluation.quality_score),
                    "reward_risk": float(evaluation.reward_risk) if evaluation.reward_risk is not None else None,
                    "rejection_reasons": evaluation.rejection_reasons,
                    "plan": evaluation.plan_json,
                }
                for evaluation, token in rows
            ],
        }

    async def core_candle_coverage(self, limit: int = 100) -> list[dict[str, object]]:
        tokens = await self.latest_core_tokens()
        coverage = []
        for token in tokens[:limit]:
            counts = {}
            latest = {}
            for timeframe in ("4h", "1h", "15m"):
                rows = await self.candles(token.address, timeframe, 240)
                counts[timeframe] = len(rows)
                latest[timeframe] = rows[-1].timestamp if rows else None
            coverage.append(
                {
                    "symbol": token.symbol,
                    "address": token.address,
                    "pool": token.primary_pool_address,
                    "candle_counts": counts,
                    "latest_candles": latest,
                    "has_strategy_history": counts["4h"] >= 35 and counts["1h"] >= 35 and counts["15m"] >= 22,
                }
            )
        return coverage


def plan_to_json(plan: TradePlan) -> dict:
    return {
        "token": {
            "address": plan.token.address,
            "symbol": plan.token.symbol,
            "name": plan.token.name,
            "pool": plan.token.primary_pool_address,
        },
        "strategy_version": plan.strategy_version,
        "quality_score": plan.quality_score,
        "regime": plan.regime.value,
        "entry_low": plan.entry_low,
        "entry_high": plan.entry_high,
        "reference_entry": plan.reference_entry,
        "stop_loss": plan.stop_loss,
        "targets": list(plan.targets),
        "reward_risk": plan.reward_risk,
        "expectancy_r": plan.expectancy_r,
        "fingerprint": plan.fingerprint,
        "reasons": plan.reasons,
        "risks": plan.risks,
    }
