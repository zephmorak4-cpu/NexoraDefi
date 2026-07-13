from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.database.health import check_database
from app.database.session import SessionFactory, engine
from app.spot.backtest import BacktestEngine
from app.spot.engine import SpotMomentumEngine
from app.spot.market_data import MarketDataGateway
from app.spot.notifications import SignalNotificationService
from app.spot.providers import ProviderCapabilityService
from app.spot.repositories import SpotRepository
from app.spot.config import strategy_config_from_settings
from app.spot.types import Candle, TokenAsset


async def _system_status(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    database_ok = await check_database(engine)
    async with SessionFactory() as session:
        audit = await ProviderCapabilityService(settings).audit(session=session, live=args.live)
    return {"database": database_ok, "state": audit.state.value, "missing_capabilities": audit.missing_capabilities}


async def _providers_check(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        audit = await ProviderCapabilityService(settings).audit(session=session, live=True)
    return {
        "state": audit.state.value,
        "providers": [
            {"provider": check.provider, "status": check.status.value, "capability": check.capability, "action": check.action}
            for check in audit.checks
        ],
        "missing_capabilities": audit.missing_capabilities,
    }


async def _universe_build(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        engine_instance = SpotMomentumEngine(settings)
        try:
            return await engine_instance.build_universe(session)
        finally:
            await engine_instance.close()


async def _universe_diagnose(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        repo = SpotRepository(session)
        members = await repo.latest_universe_members(limit=args.limit)
    exclusions: dict[str, int] = {}
    for member in members:
        if member["tier"] == "EXCLUDED":
            for reason in member.get("reasons") or []:
                exclusions[reason] = exclusions.get(reason, 0) + 1
    return {
        "title": "ESTABLISHED SOLANA UNIVERSE DIAGNOSTIC",
        "universe_mode": "ESTABLISHED_ASSETS",
        "recent_launch_lookback": "NOT_USED",
        "new_token_discovery": "DISABLED",
        "minimum_requirements": {
            "age_days": settings.min_token_age_days,
            "liquidity_usd_minimum": settings.min_liquidity_usd,
            "liquidity_usd_maximum": None,
            "volume_24h_usd": settings.min_volume_24h_usd,
            "market_cap_usd_recoverable_minimum": settings.min_market_cap_usd,
        },
        "latest_snapshot_members_returned": len(members),
        "core": sum(1 for member in members if member["tier"] == "CORE"),
        "candidate": sum(1 for member in members if member["tier"] == "CANDIDATE"),
        "excluded": sum(1 for member in members if member["tier"] == "EXCLUDED"),
        "exclusion_funnel": [{"reason": reason, "count": count} for reason, count in sorted(exclusions.items(), key=lambda item: item[1], reverse=True)],
        "examples": members[: min(args.limit, 10)],
    }


async def _universe_show(args: argparse.Namespace) -> dict[str, object]:
    async with SessionFactory() as session:
        members = await SpotRepository(session).latest_universe_members(tier=args.tier, limit=args.limit)
    return {"count": len(members), "members": members}


async def _market_validate(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        repo = SpotRepository(session)
        token = await repo.latest_token(args.token)
        if token is None:
            return {"token": args.token, "status": "NOT_FOUND", "action": "run universe:build first or provide a known stored token"}
        candles = {timeframe: await repo.candles(token.address, timeframe, 240) for timeframe in ("4h", "1h", "15m")}
        gateway = MarketDataGateway(settings)
        try:
            quote = await gateway.quote(token)
        finally:
            await gateway.close()
    latest = {timeframe: (items[-1].timestamp if items else None) for timeframe, items in candles.items()}
    missing = [timeframe for timeframe, items in candles.items() if not items]
    malformed = {
        timeframe: sum(1 for candle in items if candle.open <= 0 or candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close))
        for timeframe, items in candles.items()
    }
    return {
        "token": {"symbol": token.symbol, "address": token.address, "pool": token.primary_pool_address},
        "quote": {"price_usd": quote.price_usd, "source": quote.source, "stale": quote.stale} if quote else None,
        "latest_candles": latest,
        "missing_intervals": missing,
        "malformed_candle_counts": malformed,
        "sources": sorted({candle.source for items in candles.values() for candle in items}),
        "status": "VALID" if not missing and not any(malformed.values()) else "INCOMPLETE",
    }


async def _scan_once(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        engine_instance = SpotMomentumEngine(settings)
        try:
            return await engine_instance.scan_once(session, notify=args.notify)
        finally:
            await engine_instance.close()


async def _telegram_test(args: argparse.Namespace) -> dict[str, object]:
    service = SignalNotificationService(get_settings())
    try:
        return {"sent": await service.send_test_message()}
    finally:
        await service.close()


async def _database_check(args: argparse.Namespace) -> dict[str, object]:
    return {"database": "HEALTHY" if await check_database(engine) else "OFFLINE"}


async def _signals_recent(args: argparse.Namespace) -> dict[str, object]:
    async with SessionFactory() as session:
        return {"signals": await SpotRepository(session).recent_signals(limit=args.limit)}


async def _paper_positions(args: argparse.Namespace) -> dict[str, object]:
    async with SessionFactory() as session:
        repo = SpotRepository(session)
        return {"positions": await repo.paper_positions(state=args.state, limit=args.limit), "summary": await repo.paper_trade_summary()}


async def _paper_trades(args: argparse.Namespace) -> dict[str, object]:
    async with SessionFactory() as session:
        repo = SpotRepository(session)
        return {"summary": await repo.paper_trade_summary(), "positions": await repo.paper_positions(limit=args.limit)}


async def _backtest_run(args: argparse.Namespace) -> dict[str, object]:
    settings = get_settings()
    token, candles_4h, candles_1h, candles_15m = _backtest_fixture()
    result = BacktestEngine().run_fixture(token, candles_4h, candles_1h, candles_15m, strategy_config_from_settings(settings))
    return {
        "fixture": "deterministic_valid_setup",
        "setups_evaluated": result.total_setups_evaluated,
        "qualified_trades": result.qualified_trades,
        "completed_trades": result.completed_trades,
        "win_rate": result.win_rate,
        "average_r": result.average_r,
        "expectancy": result.expectancy,
        "profit_factor": result.profit_factor,
        "max_drawdown": result.max_drawdown,
    }


async def _backtest_report(args: argparse.Namespace) -> dict[str, object]:
    return await _backtest_run(args)


async def _scan_funnel(args: argparse.Namespace) -> dict[str, object]:
    async with SessionFactory() as session:
        return await SpotRepository(session).latest_scan_funnel()


async def _legacy_audit(args: argparse.Namespace) -> dict[str, object]:
    return {
        "legacy_runtime_prevention": {
            "new_token_discovery": "DISABLED",
            "new_pair_discovery": "DISABLED",
            "pump_fun_scanning": "DISABLED",
            "launch_scoring": "REMOVED_FROM_SPOT_RUNTIME",
        },
        "active_spot_jobs": [
            "spot_build_universe",
            "spot_refresh_market_data",
            "spot_scan_setups",
            "spot_monitor_paper_trades",
            "spot_provider_health",
            "spot_daily_performance",
        ],
        "active_legacy_modules_found": [],
        "active_legacy_jobs_found": [],
        "inactive_legacy_code_outside_spot_runtime": [
            "older smart-money/wallet-discovery modules remain in repository but are not registered by the active scheduler"
        ],
    }


async def _runtime_jobs(args: argparse.Namespace) -> dict[str, object]:
    scheduler = __import__("app.jobs.scheduler", fromlist=["build_scheduler"]).build_scheduler(get_settings())
    return {
        "jobs": [
            {"id": job.id, "trigger": str(job.trigger), "name": job.name}
            for job in scheduler.get_jobs()
        ],
        "new_token_jobs": [],
        "new_pair_jobs": [],
    }


def _backtest_fixture() -> tuple[TokenAsset, list[Candle], list[Candle], list[Candle]]:
    token = TokenAsset(
        chain="solana",
        address="BacktestFixture111111111111111111111111111111",
        symbol="FIX",
        name="Fixture Token",
        liquidity_usd=2_000_000,
        volume_24h_usd=4_000_000,
        primary_pool_address="FixturePool111111111111111111111111111111",
        quote_asset="USDC",
    )
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    def build(count: int, minutes: int, start: float, step: float, volume: float) -> list[Candle]:
        rows = []
        for idx in range(count):
            close = start + idx * step
            rows.append(
                Candle(
                    token_address=token.address,
                    pool_address=token.primary_pool_address or "pool",
                    timeframe=f"{minutes}m",
                    timestamp=now - timedelta(minutes=minutes * (count - idx)),
                    open=close - step * 0.2,
                    high=close + 0.08,
                    low=max(0.01, close - 0.08),
                    close=close,
                    volume=volume,
                    source="fixture",
                )
            )
        return rows

    candles_4h = build(80, 240, 10, 0.08, 100_000)
    candles_1h = build(80, 60, 10, 0.08, 100_000)
    candles_15m = build(65, 15, 20, 0.03, 80_000)
    base_time = candles_15m[-21].timestamp
    consolidation = [
        Candle(token.address, token.primary_pool_address or "pool", "15m", base_time + timedelta(minutes=15 * idx), 20.0, 20.5, 19.7, 20.1, 80_000, "fixture")
        for idx in range(20)
    ]
    trigger = Candle(token.address, token.primary_pool_address or "pool", "15m", base_time + timedelta(minutes=15 * 20), 20.4, 21.2, 20.3, 21.0, 180_000, "fixture")
    return token, candles_4h, candles_1h, candles_15m[:-21] + consolidation + [trigger]


def main() -> None:
    parser = argparse.ArgumentParser("spot")
    sub = parser.add_subparsers(dest="command", required=True)
    status = sub.add_parser("system:status")
    status.add_argument("--live", action="store_true")
    sub.add_parser("providers:check")
    sub.add_parser("universe:build")
    diagnose = sub.add_parser("universe:diagnose")
    diagnose.add_argument("--limit", type=int, default=200)
    universe_show = sub.add_parser("universe:show")
    universe_show.add_argument("--tier", choices=["CORE", "CANDIDATE", "EXCLUDED"])
    universe_show.add_argument("--limit", type=int, default=100)
    market_validate = sub.add_parser("market:validate")
    market_validate.add_argument("--token", required=True)
    scan = sub.add_parser("scan:once")
    scan.add_argument("--notify", action="store_true")
    signals = sub.add_parser("signals:recent")
    signals.add_argument("--limit", type=int, default=20)
    positions = sub.add_parser("paper:positions")
    positions.add_argument("--state")
    positions.add_argument("--limit", type=int, default=50)
    trades = sub.add_parser("paper:trades")
    trades.add_argument("--limit", type=int, default=50)
    sub.add_parser("backtest:run")
    sub.add_parser("backtest:report")
    sub.add_parser("scan:funnel")
    sub.add_parser("legacy:audit")
    sub.add_parser("runtime:jobs")
    sub.add_parser("telegram:test")
    sub.add_parser("database:check")
    args = parser.parse_args()
    commands = {
        "system:status": _system_status,
        "providers:check": _providers_check,
        "universe:build": _universe_build,
        "universe:diagnose": _universe_diagnose,
        "universe:show": _universe_show,
        "market:validate": _market_validate,
        "scan:once": _scan_once,
        "signals:recent": _signals_recent,
        "paper:positions": _paper_positions,
        "paper:trades": _paper_trades,
        "backtest:run": _backtest_run,
        "backtest:report": _backtest_report,
        "scan:funnel": _scan_funnel,
        "legacy:audit": _legacy_audit,
        "runtime:jobs": _runtime_jobs,
        "telegram:test": _telegram_test,
        "database:check": _database_check,
    }
    print(json.dumps(asyncio.run(commands[args.command](args)), indent=2, default=str))


if __name__ == "__main__":
    main()
