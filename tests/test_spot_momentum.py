from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest

from app.core.config import Settings
from app.integrations.market_data_clients import DexScreenerClient, GeckoTerminalClient
from app.services.http import AsyncAPIClient
from app.spot.backtest import BacktestEngine
from app.spot.indicators import atr, ema, validate_closed_candles
from app.spot.market_data import MarketDataGateway
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
    def dex_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token-profiles/latest/v1":
            return httpx.Response(200, json=[{"chainId": "solana", "tokenAddress": "TokenA"}])
        if request.url.path == "/token-pairs/v1/solana/TokenA":
            return httpx.Response(200, json=[{"chainId": "solana", "pairAddress": "PoolA", "dexId": "orca", "baseToken": {"address": "TokenA", "symbol": "TOK", "name": "Token"}, "quoteToken": {"symbol": "USDC"}, "liquidity": {"usd": "1000000"}, "volume": {"h24": "2000000"}, "marketCap": "10000000"}])
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
    tokens = await gateway.discover_solana_candidates()
    assert tokens[0].address == "TokenA"
    assert {token.address for token in tokens} == {"TokenA", "TokenB"}
    assert (await gateway.candles(tokens[0], "15m"))[0].close == 1.5
    await gateway.close()
