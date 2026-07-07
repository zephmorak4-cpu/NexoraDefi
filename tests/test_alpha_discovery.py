from contextlib import asynccontextmanager

import httpx
from sqlalchemy import select

from app.alpha_discovery import api as alpha_api
from app.alpha_discovery.agents import DecisionAgent, LaunchQualityAgent, RiskAgent
from app.alpha_discovery.engine import SolanaAlphaDiscoveryEngine
from app.alpha_discovery.format_alert import format_alpha_alert
from app.alpha_discovery.services import MarketDataService
from app.alpha_discovery.types import AgentScore, RiskScore, SmartMoneyScore, TokenLaunch, TokenTxns
from app.core.config import Settings
from app.main import app
from app.models import AlphaAlertHistory, AlphaScannedToken


def _launch(**overrides):
    values = {
        "token_address": "AlphaToken1111111111111111111111111111111111",
        "pair_address": "AlphaPair11111111111111111111111111111111111",
        "symbol": "ALPHA",
        "name": "Alpha Token",
        "dex": "raydium",
        "source": "test",
        "liquidity_usd": 42_000,
        "market_cap_usd": 180_000,
        "price_usd": 0.001,
        "volume_usd": 95_000,
        "txns": TokenTxns(buys=90, sells=20),
    }
    values.update(overrides)
    return TokenLaunch(**values)


class FakeMarketData:
    def __init__(self, launches):
        self.launches = launches

    async def latest_solana_launches(self):
        return self.launches

    async def close(self):
        return None


class FakeTelegram:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(message)
        return True

    async def close(self):
        return None


class FakeDexClient:
    async def request_json(self, method, path):
        if path == "/token-profiles/latest/v1":
            return [{"chainId": "solana", "tokenAddress": "FallbackToken"}]
        raise RuntimeError("pair unavailable")

    async def close(self):
        return None


class FixedAgent:
    def __init__(self, score):
        self.score_value = score

    def score(self, token):
        return AgentScore(self.score_value, True, [f"fixed score {self.score_value}"])


class FixedSmartMoneyAgent:
    def score(self, token):
        return SmartMoneyScore(100, True, ["4 smart wallets accumulated early"], 4)


class FixedRiskAgent:
    def score(self, token):
        return RiskScore(95, True, ["risk checks passed"], "LOW")


def test_launch_quality_rejects_low_liquidity():
    score = LaunchQualityAgent(Settings(alpha_min_liquidity_usd=5_000)).score(_launch(liquidity_usd=499))

    assert not score.passed
    assert "liquidity too low" in score.reasons


def test_risk_agent_rejects_concentrated_supply():
    score = RiskAgent(Settings()).score(_launch(creator_hold_percent=25, top10_holder_percent=70))

    assert not score.passed
    assert score.risk_level in {"HIGH", "EXTREME"}
    assert "creator holding too high" in score.reasons
    assert "top 10 holder concentration too high" in score.reasons


def test_decision_agent_only_alerts_for_high_confidence_alpha():
    decision = DecisionAgent(Settings()).decide(
        AgentScore(100, True, ["launch quality passed"]),
        AgentScore(95, True, ["developer clean"]),
        SmartMoneyScore(100, True, ["smart wallets detected"], 4),
        AgentScore(100, True, ["strong momentum"]),
        RiskScore(95, True, ["low risk"], "LOW"),
    )

    assert decision.decision == "ALPHA_ALERT"
    assert decision.should_alert is True
    assert decision.final_score >= 90


async def test_engine_persists_scan_and_sends_alert_without_trade_execution(db_session):
    telegram = FakeTelegram()
    engine = SolanaAlphaDiscoveryEngine(
        db_session,
        Settings(telegram_alerts_enabled=True),
        market_data=FakeMarketData([_launch()]),
        telegram=telegram,
    )
    engine.developer = FixedAgent(95)
    engine.smart_money = FixedSmartMoneyAgent()
    engine.risk = FixedRiskAgent()

    counts = await engine.scan()

    scanned = await db_session.scalar(select(AlphaScannedToken))
    alert = await db_session.scalar(select(AlphaAlertHistory))
    assert counts == {"scanned": 1, "alerts": 1, "watchlist": 0, "rejected": 0}
    assert scanned.token_address == "AlphaToken1111111111111111111111111111111111"
    assert scanned.should_alert is True
    assert alert.channel == "telegram"
    assert len(telegram.messages) == 1
    assert "Alert only. No auto-buying" in telegram.messages[0]


async def test_market_data_profile_fallback_when_pair_lookup_fails():
    market_data = MarketDataService(Settings(), client=FakeDexClient())

    launches = await market_data.latest_solana_launches()

    assert len(launches) == 1
    assert launches[0].token_address == "FallbackToken"
    assert launches[0].source == "dexscreener-profile"
    await market_data.close()


def test_alpha_alert_message_explains_addresses_and_manual_review():
    message = format_alpha_alert(
        _launch(),
        DecisionAgent(Settings()).decide(
            AgentScore(100, True, ["launch quality passed"]),
            AgentScore(95, True, ["developer clean"]),
            SmartMoneyScore(100, True, ["smart wallets detected"], 4),
            AgentScore(100, True, ["strong momentum"]),
            RiskScore(95, True, ["low risk"], "LOW"),
        ),
        RiskScore(95, True, ["low risk"], "LOW"),
        SmartMoneyScore(100, True, ["smart wallets detected"], 4),
    )

    assert "Token Address:" in message
    assert "Pair Address:" in message
    assert "Overall Alpha Score:" in message
    assert "Review manually" in message


async def test_alpha_admin_api_returns_plain_english_token_breakdown(db_session, monkeypatch):
    db_session.add(
        AlphaScannedToken(
            token_address="ApiToken",
            pair_address="ApiPair",
            symbol="API",
            name="API Token",
            source="test",
            buys=10,
            sells=2,
            final_score=91,
            decision="ALPHA_ALERT",
            should_alert=True,
            rejection_reasons=["smart wallets detected"],
            agent_scores={"smart_money": 100},
        )
    )
    await db_session.commit()

    @asynccontextmanager
    async def fake_session_factory():
        yield db_session

    monkeypatch.setattr(alpha_api, "SessionFactory", fake_session_factory)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        tokens = await client.get("/admin/alpha/tokens")
        audit = await client.get("/admin/alpha/audit")

    payload = tokens.json()[0]
    assert payload["token"]["address"] == "ApiToken"
    assert payload["token"]["pair_address"] == "ApiPair"
    assert payload["assessment"]["decision"] == "ALPHA_ALERT"
    assert audit.json()["mode"] == "alert_only"
