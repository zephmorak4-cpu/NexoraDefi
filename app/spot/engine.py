from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.spot.config import strategy_config_from_settings
from app.spot.market_data import MarketDataGateway
from app.spot.notifications import SignalNotificationService
from app.spot.paper import PaperBroker
from app.spot.providers import ProviderCapabilityService
from app.spot.repositories import SpotRepository
from app.spot.strategy import TrendAlignedVolatilityExpansion
from app.spot.types import ReadinessState, SignalDecision
from app.spot.universe import UniverseBuilder


@dataclass(frozen=True)
class ScanFunnel:
    core_tokens: int
    regime_permitted: int = 0
    trend_aligned: int = 0
    valid_consolidation: int = 0
    confirmed_breakout: int = 0
    volume_confirmed: int = 0
    valid_reward_risk: int = 0
    signals_generated: int = 0
    rejection_reasons: list[dict[str, int]] | None = None


class SpotMomentumEngine:
    def __init__(self, settings: Settings, market_data: MarketDataGateway | None = None) -> None:
        self.settings = settings
        self.market_data = market_data or MarketDataGateway(settings)
        self.strategy = TrendAlignedVolatilityExpansion()
        self.config = strategy_config_from_settings(settings)

    async def build_universe(self, session: AsyncSession) -> dict[str, object]:
        tokens = await self.market_data.discover_solana_candidates()
        build = UniverseBuilder(self.settings).build(tokens)
        await SpotRepository(session).save_universe(build)
        await session.commit()
        return {
            "snapshot_id": build.snapshot_id,
            "candidates_discovered": build.candidates_discovered,
            "eligible": len(build.eligible),
            "core": len(build.core),
            "candidate": len(build.candidate),
            "excluded": len(build.excluded),
            "exclusion_summary": build.exclusion_summary,
        }

    async def refresh_market_data(self, session: AsyncSession, limit: int = 200) -> dict[str, int]:
        repo = SpotRepository(session)
        tokens = await repo.latest_core_tokens()
        counts = {"tokens": len(tokens), "candles": 0}
        for token in tokens:
            for timeframe in ("4h", "1h", "15m"):
                candles = await self.market_data.candles(token, timeframe, limit)
                await repo.upsert_candles(candles)
                counts["candles"] += len(candles)
        await session.commit()
        return counts

    async def scan_once(self, session: AsyncSession, notify: bool = True) -> dict[str, object]:
        audit = await ProviderCapabilityService(self.settings).audit(session=session, live=True)
        if audit.state == ReadinessState.NOT_READY:
            return {"state": audit.state.value, "signals": 0, "missing_capabilities": audit.missing_capabilities}
        repo = SpotRepository(session)
        tokens = await repo.latest_core_tokens()
        scan_id = uuid4().hex
        broker = PaperBroker(self.settings)
        notifier = SignalNotificationService(self.settings)
        rejection_counter: Counter[str] = Counter()
        signals = 0
        for token in tokens:
            result = self.strategy.evaluate(
                token,
                await repo.candles(token.address, "4h", 240),
                await repo.candles(token.address, "1h", 240),
                await repo.candles(token.address, "15m", 240),
                self.config,
            )
            await repo.save_evaluation(scan_id, result, self.config.version)
            if result.decision == SignalDecision.QUALIFIED and result.plan:
                if await repo.signal_exists(result.plan.fingerprint):
                    rejection_counter["duplicate setup"] += 1
                    continue
                await repo.save_signal(result.plan)
                await broker.create_waiting_position(session, result.plan)
                if notify:
                    await notifier.send_signal(result.plan)
                signals += 1
            else:
                rejection_counter.update(result.reasons or ["rejected"])
        await notifier.close()
        await session.commit()
        return {
            "state": ReadinessState.READY_FOR_BACKTESTING.value,
            "scan_id": scan_id,
            "funnel": {
                "tokens_in_core_universe": len(tokens),
                "signals_generated": signals,
                "primary_rejection_reasons": [{"reason": reason, "count": count} for reason, count in rejection_counter.most_common(10)],
            },
            "tokens_evaluated": len(tokens),
            "signals": signals,
            "rejection_reasons": [{"reason": reason, "count": count} for reason, count in rejection_counter.most_common(10)],
        }

    async def close(self) -> None:
        await self.market_data.close()
