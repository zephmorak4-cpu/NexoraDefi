from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings
from app.integrations.market_data_clients import BirdeyeClient, DexScreenerClient, GeckoTerminalClient
from app.services.http import AsyncAPIClient
from app.spot.backtest import BacktestEngine
from app.spot.indicators import atr, ema, validate_closed_candles
from app.spot.market_data import MarketDataGateway
from app.spot.notifications import format_operational_alert
from app.spot.paper import PaperBroker
from app.spot.providers import ProviderCapabilityService, ProviderStatus
from app.spot.strategy import TrendAlignedVolatilityExpansion
from app.spot.types import Candle, PaperTradeState, SignalDecision, StrategyConfig, TokenAsset
from app.spot.universe import UniverseBuilder


def candles(count: int, start: float = 10, step: float = 0.05, volume: float = 1000, timeframe: str = "15m") -> list[Candle]:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(count):
        close = start + i * step
        rows.append(
            Candle(
                token_address="TokenA",
                pool_address="PoolA",
                timeframe=timeframe,
                timestamp=base + timedelta(minutes=15 * i),
                open=close - 0.02,
                high=close + 0.05,
                low=close - 0.05,
                close=close,
                volume=volume,
                source="fixture",
            )
        )
    return rows


def valid_setup_fixture() -> tuple[TokenAsset, list[Candle], list[Candle], list[Candle]]:
    token = TokenAsset(chain="solana", address="TokenA", symbol="TOK", name="Token", liquidity_usd=1_000_000, volume_24h_usd=2_000_000, market_cap_usd=10_000_000, primary_pool_address="PoolA", quote_asset="USDC")
    c4h = candles(80, start=8, step=0.08, timeframe="4h")
    c1h = candles(80, start=8, step=0.06, timeframe="1h")
    c15 = candles(60, start=10, step=0.0, volume=1000, timeframe="15m")
    for i in range(40, 59):
        price = 11 + (i % 4) * 0.02
        c15[i] = Candle("TokenA", "PoolA", "15m", c15[i].timestamp, price, price + 0.08, price - 0.08, price, 1000, "fixture")
    c15[-1] = Candle("TokenA", "PoolA", "15m", c15[-1].timestamp, 11.1, 11.8, 11.05, 11.75, 3000, "fixture")
    return token, c4h, c1h, c15


def test_ema_and_atr_are_deterministic():
    assert ema([1, 2, 3], 2)[-1] == pytest.approx(2.5555555556)
    values = atr(candles(20), 14)
    assert len(values) == 20
    assert values[-1] > 0


def test_malformed_candles_are_rejected():
    bad = [Candle("T", "P", "15m", datetime.now(timezone.utc), 10, 9, 8, 10, 1, "fixture")]
    assert "malformed OHLC relationship" in validate_closed_candles(bad)


def test_valid_bullish_setup_produces_trade_plan():
    token, c4h, c1h, c15 = valid_setup_fixture()
    result = TrendAlignedVolatilityExpansion().evaluate(token, c4h, c1h, c15, StrategyConfig(min_quality_score=60, max_consolidation_atr=20, max_stop_distance_percent=20))
    assert result.decision == SignalDecision.QUALIFIED
    assert result.plan is not None
    assert result.plan.reward_risk >= 2
    assert result.plan.stop_loss < result.plan.reference_entry < result.plan.targets[1]


def test_breakout_without_volume_is_rejected():
    token, c4h, c1h, c15 = valid_setup_fixture()
    c15[-1] = Candle("TokenA", "PoolA", "15m", c15[-1].timestamp, 11.1, 11.8, 11.05, 11.75, 500, "fixture")
    result = TrendAlignedVolatilityExpansion().evaluate(token, c4h, c1h, c15, StrategyConfig(min_quality_score=60, max_consolidation_atr=20))
    assert result.decision == SignalDecision.REJECTED
    assert "breakout volume confirmation failed" in result.reasons


def test_wick_without_closed_breakout_is_rejected():
    token, c4h, c1h, c15 = valid_setup_fixture()
    c15[-1] = Candle("TokenA", "PoolA", "15m", c15[-1].timestamp, 11.1, 11.8, 11.05, 11.05, 3000, "fixture")
    result = TrendAlignedVolatilityExpansion().evaluate(token, c4h, c1h, c15, StrategyConfig(min_quality_score=60, max_consolidation_atr=20))
    assert result.decision == SignalDecision.REJECTED


def test_universe_filters_and_ranks_tokens():
    settings = Settings(min_token_age_days=1, min_liquidity_usd=100, min_volume_24h_usd=100, min_market_cap_usd=100, target_universe_size=1, candidate_universe_size=2)
    good = TokenAsset(chain="solana", address="A", symbol="AAA", name="A", liquidity_usd=1000, volume_24h_usd=1000, market_cap_usd=1000, primary_pool_address="P", quote_asset="USDC")
    bad = TokenAsset(chain="solana", address="B", symbol="USDC", name="USD Coin", liquidity_usd=999999, volume_24h_usd=999999, market_cap_usd=999999, primary_pool_address="P", quote_asset="USDC")
    build = UniverseBuilder(settings).build([bad, good])
    assert build.core[0].token.address == "A"
    assert build.excluded[0].reasons


def test_established_high_liquidity_token_is_eligible_without_liquidity_ceiling():
    token = TokenAsset(
        chain="solana",
        address="EstablishedHighLiquidity",
        symbol="HIGH",
        name="High Liquidity",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        liquidity_usd=25_000_000,
        volume_24h_usd=12_000_000,
        market_cap_usd=300_000_000,
        primary_pool_address="Pool",
        quote_asset="USDC",
    )
    build = UniverseBuilder(Settings()).build([token])
    assert build.core[0].token.address == token.address
    assert build.excluded == []


def test_mature_token_at_minimum_liquidity_is_eligible():
    token = TokenAsset(
        chain="solana",
        address="EstablishedMinimumLiquidity",
        symbol="MIN",
        name="Minimum Liquidity",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        liquidity_usd=550_000,
        volume_24h_usd=1_500_000,
        market_cap_usd=20_000_000,
        primary_pool_address="Pool",
        quote_asset="SOL",
    )
    build = UniverseBuilder(Settings()).build([token])
    assert build.core[0].token.address == token.address


def test_new_token_with_strong_liquidity_is_excluded_only_by_age():
    token = TokenAsset(
        chain="solana",
        address="ImmatureToken",
        symbol="YOUNG",
        name="Young",
        created_at=datetime.now(timezone.utc) - timedelta(days=3),
        liquidity_usd=2_000_000,
        volume_24h_usd=8_000_000,
        market_cap_usd=50_000_000,
        primary_pool_address="Pool",
        quote_asset="USDC",
    )
    build = UniverseBuilder(Settings()).build([token])
    assert build.excluded[0].token.address == token.address
    assert build.excluded[0].reasons == ["insufficient age"]


def test_pump_fun_style_assets_are_excluded_from_established_universe():
    token = TokenAsset(
        chain="solana",
        address="pumpCmXqMfrsAkQ5r49WcJnRayYRqmXz6ae8H7H9Dfn",
        symbol="PUMP",
        name="Pump",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        liquidity_usd=25_000_000,
        volume_24h_usd=30_000_000,
        market_cap_usd=300_000_000,
        primary_pool_address="Pool",
        quote_asset="USDC",
    )
    build = UniverseBuilder(Settings()).build([token])
    assert build.core == []
    assert "pump.fun launch asset excluded" in build.excluded[0].reasons


def test_operational_alert_formatter_omits_secret_like_fields():
    message = format_operational_alert(
        "SYSTEM_READY",
        "READY",
        {"database": "healthy", "api_key": "secret", "bot_token": "secret"},
    )
    assert "database: healthy" in message
    assert "secret" not in message
    assert "api_key" not in message


def test_null_market_cap_does_not_force_zero_rejection_when_other_critical_fields_pass():
    token = TokenAsset(
        chain="solana",
        address="NullMarketCapToken",
        symbol="NULLMC",
        name="Null Market Cap",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        liquidity_usd=5_000_000,
        volume_24h_usd=3_000_000,
        market_cap_usd=None,
        fdv_usd=None,
        primary_pool_address="Pool",
        quote_asset="USDC",
    )
    build = UniverseBuilder(Settings()).build([token])
    assert build.core[0].token.address == token.address


def test_established_token_with_new_secondary_pool_keeps_oldest_age():
    older = TokenAsset(
        chain="solana",
        address="SameToken",
        symbol="SAME",
        name="Same",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        liquidity_usd=1_000_000,
        volume_24h_usd=2_000_000,
        market_cap_usd=20_000_000,
        primary_pool_address="OldPool",
        quote_asset="USDC",
    )
    newer = TokenAsset(
        chain="solana",
        address="SameToken",
        symbol="SAME",
        name="Same",
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
        liquidity_usd=2_000_000,
        volume_24h_usd=3_000_000,
        market_cap_usd=20_000_000,
        primary_pool_address="NewPool",
        quote_asset="USDC",
    )
    tokens = {older.address: older}
    MarketDataGateway._add_best(tokens, newer)
    build = UniverseBuilder(Settings()).build(list(tokens.values()))
    assert build.core[0].token.address == "SameToken"
    assert build.core[0].token.created_at == older.created_at


async def test_provider_audit_reports_missing_telegram_when_enabled(db_session):
    settings = Settings(telegram_signals_enabled=True, telegram_bot_token=None, telegram_chat_id=None)
    audit = await ProviderCapabilityService(settings).audit(session=db_session, live=False)
    assert "Telegram notifications" in audit.missing_capabilities


def test_paper_broker_conservative_intrabar_stop_first():
    settings = Settings(signal_min_quality_score=60)
    token, c4h, c1h, c15 = valid_setup_fixture()
    plan = TrendAlignedVolatilityExpansion().evaluate(token, c4h, c1h, c15, StrategyConfig(min_quality_score=60, max_consolidation_atr=20, max_stop_distance_percent=20)).plan
    assert plan is not None
    broker = PaperBroker(settings)
    from app.models import PaperPosition

    position = PaperPosition(signal_fingerprint=plan.fingerprint, token_address=token.address, state=PaperTradeState.OPEN.value, entry_price=Decimal(str(plan.reference_entry)), quantity=Decimal("10"), stop_loss=Decimal(str(plan.stop_loss)), target_1=Decimal(str(plan.targets[0])), target_2=Decimal(str(plan.targets[1])), target_3=Decimal(str(plan.targets[2])))
    candle = Candle(token.address, "PoolA", "15m", datetime.now(timezone.utc), plan.reference_entry, plan.targets[2], plan.stop_loss * 0.99, plan.reference_entry, 1000, "fixture")
    result = broker.update_open_position(position, candle)
    assert result.state == PaperTradeState.CLOSED_SL


def test_backtest_uses_same_strategy_fixture():
    token, c4h, c1h, c15 = valid_setup_fixture()
    result = BacktestEngine().run_fixture(token, c4h, c1h, c15, StrategyConfig(min_quality_score=60, max_consolidation_atr=20, max_stop_distance_percent=20))
    assert result.total_setups_evaluated == 1
    assert result.qualified_trades == 1


async def test_market_data_gateway_normalizes_dexscreener_and_gecko():
    seen_paths: list[str] = []

    def dex_handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/latest/dex/search":
            return httpx.Response(200, json={"pairs": [{"chainId": "solana", "pairAddress": "PoolB", "dexId": "raydium", "baseToken": {"address": "TokenB", "symbol": "JUP", "name": "Jupiter"}, "quoteToken": {"symbol": "USDC"}, "liquidity": {"usd": "3000000"}, "volume": {"h24": "5000000"}, "marketCap": "100000000"}]})
        return httpx.Response(404)

    def gecko_handler(request: httpx.Request) -> httpx.Response:
        if "ohlcv" in request.url.path:
            return httpx.Response(200, json={"data": {"attributes": {"ohlcv_list": [[1780000000, 1, 2, 0.5, 1.5, 100]]}}})
        return httpx.Response(200, json={"data": []})

    settings = Settings()
    dex = DexScreenerClient(settings, AsyncAPIClient("https://api.dexscreener.com", client=httpx.AsyncClient(base_url="https://api.dexscreener.com", transport=httpx.MockTransport(dex_handler))))
    gecko = GeckoTerminalClient(settings, AsyncAPIClient("https://api.geckoterminal.com/api/v2", client=httpx.AsyncClient(base_url="https://api.geckoterminal.com/api/v2", transport=httpx.MockTransport(gecko_handler))))
    gateway = MarketDataGateway(settings, dex, gecko)
    tokens = await gateway.retrieve_universe_candidates()
    assert "/token-profiles/latest/v1" not in seen_paths
    assert {token.address for token in tokens} == {"TokenB"}
    assert (await gateway.candles(tokens[0], "15m"))[0].close == 1.5
    await gateway.close()


async def test_market_data_gateway_uses_birdeye_ohlcv_fallback():
    token = TokenAsset(chain="solana", address="TokenA", symbol="TOK", name="Token", primary_pool_address="PoolA")

    def dex_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    def gecko_handler(request: httpx.Request) -> httpx.Response:
        if "ohlcv" in request.url.path:
            return httpx.Response(429, json={"message": "rate limited"})
        return httpx.Response(200, json={"data": []})

    def birdeye_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/defi/ohlcv":
            return httpx.Response(200, json={"data": {"items": [{"unixTime": 1780000000, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}]}})
        if request.url.path == "/defi/price":
            return httpx.Response(200, json={"success": True, "data": {"value": 1.25, "liquidity": 1000}})
        return httpx.Response(404)

    settings = Settings(birdeye_api_key="test")
    dex = DexScreenerClient(settings, AsyncAPIClient("https://api.dexscreener.com", client=httpx.AsyncClient(base_url="https://api.dexscreener.com", transport=httpx.MockTransport(dex_handler))))
    gecko = GeckoTerminalClient(settings, AsyncAPIClient("https://api.geckoterminal.com/api/v2", client=httpx.AsyncClient(base_url="https://api.geckoterminal.com/api/v2", transport=httpx.MockTransport(gecko_handler))))
    birdeye = BirdeyeClient(settings, AsyncAPIClient("https://public-api.birdeye.so", client=httpx.AsyncClient(base_url="https://public-api.birdeye.so", transport=httpx.MockTransport(birdeye_handler))))
    gateway = MarketDataGateway(settings, dex, gecko, birdeye)
    assert (await gateway.candles(token, "15m"))[0].source == "Birdeye"
    assert (await gateway.quote(token)).source == "Birdeye"
    await gateway.close()


async def test_established_universe_retrieval_reads_later_gecko_pages():
    def dex_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"pairs": []})

    def gecko_handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        if page == "3":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "solana_pool_page3",
                            "attributes": {
                                "name": "PAGE3/USDC",
                                "dex_id": "orca",
                                "reserve_in_usd": "2000000",
                                "volume_usd": {"h24": "3000000"},
                                "market_cap_usd": "50000000",
                            },
                            "relationships": {"base_token": {"data": {"id": "solana_Page3Token"}}},
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"data": []})

    settings = Settings(universe_gecko_pages=3, universe_dex_search_queries="unused")
    dex = DexScreenerClient(settings, AsyncAPIClient("https://api.dexscreener.com", client=httpx.AsyncClient(base_url="https://api.dexscreener.com", transport=httpx.MockTransport(dex_handler))))
    gecko = GeckoTerminalClient(settings, AsyncAPIClient("https://api.geckoterminal.com/api/v2", client=httpx.AsyncClient(base_url="https://api.geckoterminal.com/api/v2", transport=httpx.MockTransport(gecko_handler))))
    gateway = MarketDataGateway(settings, dex, gecko)
    tokens = await gateway.retrieve_universe_candidates()
    assert [token.address for token in tokens] == ["Page3Token"]
    assert gateway.last_source_stats[-1]["pages_requested"] == 3
    await gateway.close()
