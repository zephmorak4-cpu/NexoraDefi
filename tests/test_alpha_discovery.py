from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from json import loads as json_loads
from zipfile import ZipFile

import httpx
from sqlalchemy import select

from app.alpha_discovery import api as alpha_api
from app.alpha_discovery import jobs as alpha_jobs
from app.alpha_discovery.agents import DecisionAgent, DeveloperReputationAgent, LaunchDetectorAgent, LaunchQualityAgent, RiskAgent, SmartMoneyAgent
from app.alpha_discovery.birdeye_provider import BirdeyeService
from app.alpha_discovery.dexscreener_provider import DexScreenerService
from app.alpha_discovery.engine import SolanaAlphaDiscoveryEngine
from app.alpha_discovery.format_alert import format_alpha_alert
from app.alpha_discovery.helius_provider import HeliusService
from app.alpha_discovery.report import AlphaDiscoveryReportExporter, build_watchlist_digest
from app.alpha_discovery.services import MarketDataService
from app.alpha_discovery.solana_rpc_provider import SolanaRPCService
from app.alpha_discovery.types import AgentScore, ProviderSnapshot, RiskScore, SmartMoneyScore, TokenLaunch, TokenTxns
from app.core.config import Settings
from app.main import app
from app.models import AlphaAlertHistory, AlphaProviderSnapshot, AlphaScannedToken, AlphaWatchlistToken, CandidateHistory, CandidateWallet, TrackedWallet, WalletActivity


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
        "volume_usd_24h": 95_000,
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


class FakeDigestTelegram(FakeTelegram):
    async def send_document(self, document_path, caption):
        return True


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
    async def score_token(self, session, token):
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


def test_unknown_creator_is_not_neutral():
    missing = DeveloperReputationAgent().score(_launch(creator_wallet=None))
    unknown = DeveloperReputationAgent().score(_launch(creator_wallet="CreatorWallet"))

    assert missing.score == 25
    assert missing.passed is False
    assert "creator wallet unavailable" in missing.reasons[0]
    assert unknown.score == 35
    assert "cautious unknown score" in unknown.reasons[0]


async def test_smart_money_agent_uses_tracked_and_candidate_wallet_activity(db_session):
    tracked = TrackedWallet(
        wallet_address="tracked-alpha-wallet",
        chain="solana",
        status="active",
        reputation_score=Decimal("95"),
    )
    candidate = CandidateWallet(
        wallet_address="candidate-alpha-wallet",
        chain="solana",
        discovery_reason="test",
        status="observing",
        candidate_score=Decimal("95"),
        reputation_score=Decimal("95"),
    )
    db_session.add_all([tracked, candidate])
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            WalletActivity(
                wallet_id=tracked.id,
                token_address="AlphaToken1111111111111111111111111111111111",
                transaction_signature="tracked-buy",
                transaction_type="buy",
                amount=Decimal("1"),
                timestamp=now,
            ),
            CandidateHistory(
                wallet_id=candidate.id,
                signature="candidate-buy",
                token="AlphaToken1111111111111111111111111111111111",
                action="buy",
                amount=Decimal("1"),
                timestamp=now,
            ),
        ]
    )
    await db_session.commit()

    score = await SmartMoneyAgent(Settings(alpha_smart_wallet_min_count=2)).score_token(db_session, _launch())

    assert score.smart_wallets_detected == 2
    assert score.score == 60
    assert "moderate confirmation" in score.reasons[0]


async def test_smart_money_agent_penalizes_no_accumulation(db_session):
    score = await SmartMoneyAgent(Settings()).score_token(db_session, _launch())

    assert score.score == 30
    assert score.passed is False
    assert "no smart wallet accumulation detected" in score.reasons


def test_low_liquidity_forces_ignore_and_caps_score():
    decision = DecisionAgent(Settings(alpha_min_liquidity_usd=5_000)).decide(
        AgentScore(100, True, ["launch quality passed"]),
        AgentScore(35, True, ["creator reputation data incomplete; cautious unknown score applied"]),
        SmartMoneyScore(30, False, ["no smart wallet accumulation detected"], 0),
        AgentScore(100, True, ["strong momentum"]),
        RiskScore(80, True, ["Top holder data unavailable"], "LOW"),
        _launch(liquidity_usd=499),
    )

    assert decision.decision == "IGNORE"
    assert decision.final_score <= 59
    assert decision.should_alert is False
    assert "liquidity below minimum; token rejected" in decision.caps_applied


def test_missing_smart_money_and_creator_caps_prevent_watchlist():
    decision = DecisionAgent(Settings()).decide(
        AgentScore(100, True, ["launch quality passed"]),
        AgentScore(25, False, ["creator wallet unavailable; high uncertainty"]),
        SmartMoneyScore(20, False, ["smart wallet transaction stream unavailable; confidence capped"], 0),
        AgentScore(100, True, ["strong momentum"]),
        RiskScore(77, True, ["Top holder data unavailable"], "MEDIUM"),
        _launch(),
    )

    assert decision.final_score <= 64
    assert decision.decision == "IGNORE"
    assert "smart wallet stream unavailable capped score at 69" in decision.caps_applied
    assert "creator wallet missing capped score at 64" in decision.caps_applied


async def test_engine_persists_scan_and_sends_alert_without_trade_execution(db_session):
    telegram = FakeTelegram()
    engine = SolanaAlphaDiscoveryEngine(
        db_session,
        Settings(telegram_alerts_enabled=True),
        market_data=FakeMarketData(
            [
                _launch(
                    provider_snapshots=[
                        ProviderSnapshot(
                            "DEXSCREENER",
                            {"pairAddress": "AlphaPair11111111111111111111111111111111111"},
                            {"liquidityUsd": 42000},
                        )
                    ],
                    sources=["DEX Screener"],
                )
            ]
        ),
        telegram=telegram,
    )
    engine.developer = FixedAgent(95)
    engine.smart_money = FixedSmartMoneyAgent()
    engine.risk = FixedRiskAgent()

    counts = await engine.scan()

    scanned = await db_session.scalar(select(AlphaScannedToken))
    alert = await db_session.scalar(select(AlphaAlertHistory))
    snapshot = await db_session.scalar(select(AlphaProviderSnapshot))
    assert counts == {"scanned": 1, "alerts": 1, "watchlist": 0, "rejected": 0}
    assert scanned.token_address == "AlphaToken1111111111111111111111111111111111"
    assert scanned.scan_id is not None
    assert scanned.should_alert is True
    assert snapshot.provider == "DEXSCREENER"
    assert alert.channel == "telegram"
    assert alert.scan_id == scanned.scan_id
    assert len(telegram.messages) == 1
    assert "Alert only. No auto-buying" in telegram.messages[0]


async def test_market_data_profile_fallback_when_pair_lookup_fails():
    market_data = MarketDataService(
        Settings(birdeye_enabled=False, helius_enabled=False, solana_rpc_enabled=False),
        client=FakeDexClient(),
    )

    launches = await market_data.latest_solana_launches()

    assert len(launches) == 1
    assert launches[0].token_address == "FallbackToken"
    assert launches[0].source == "DEXSCREENER"
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
    assert "5m Volume:" in message
    assert "Sources:" in message


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


async def test_alpha_report_exporter_creates_word_and_pdf_profiles(db_session, tmp_path):
    db_session.add(
        AlphaScannedToken(
            token_address="ReportToken",
            pair_address="ReportPair",
            symbol="RPT",
            name="Report Token",
            source="test",
            liquidity_usd=Decimal("12000"),
            market_cap_usd=Decimal("90000"),
            volume_usd=Decimal("34000"),
            buys=40,
            sells=10,
            final_score=Decimal("84"),
            decision="WATCH_CLOSELY",
            should_alert=False,
            rejection_reasons=["smart wallet signal below threshold"],
            agent_scores={"launch_quality": 100, "smart_money": 70},
        )
    )
    db_session.add(
        AlphaWatchlistToken(
            token_address="ReportToken",
            decision="WATCH_CLOSELY",
            final_score=Decimal("84"),
            reasons=["smart wallet signal below threshold"],
        )
    )
    await db_session.commit()

    export = await AlphaDiscoveryReportExporter().export(db_session, tmp_path, limit=10)

    assert export["summary"]["tokens_reviewed"] == 1
    assert (tmp_path / "Solana Alpha Discovery Report.docx").exists()
    assert (tmp_path / "Solana Alpha Discovery Report.pdf").exists()
    with ZipFile(tmp_path / "Solana Alpha Discovery Report.docx") as archive:
        document_xml = archive.read("word/document.xml").decode()
    assert "Token Address: ReportToken" in document_xml
    assert "Pair Address: ReportPair" in document_xml
    assert "Manual" in document_xml or "manual" in document_xml


def test_watchlist_digest_is_plain_english():
    digest = build_watchlist_digest(
        [
            AlphaWatchlistToken(
                token_address="WatchToken",
                decision="WATCH_CLOSELY",
                final_score=Decimal("82"),
                reasons=["strong momentum", "smart wallet signal below threshold"],
            )
        ]
    )

    assert "watchlist tokens" in digest
    assert "Address:" in digest
    assert "`WatchToken`" not in digest
    assert "Main issue:" in digest
    assert "Why:" in digest
    assert "buy instructions" in digest


async def test_watchlist_digest_excludes_monitor_only_by_default(db_session, monkeypatch):
    db_session.add_all(
        [
            AlphaWatchlistToken(
                token_address="WatchToken",
                decision="WATCH_CLOSELY",
                final_score=Decimal("84"),
                reasons=["2 smart wallets detected; moderate confirmation"],
            ),
            AlphaWatchlistToken(
                token_address="MonitorToken",
                decision="MONITOR_ONLY",
                final_score=Decimal("74"),
                reasons=["no smart wallet accumulation detected"],
            ),
        ]
    )
    await db_session.commit()

    @asynccontextmanager
    async def fake_session_factory():
        yield db_session

    telegram = FakeDigestTelegram()
    monkeypatch.setattr(alpha_jobs, "SessionFactory", fake_session_factory)
    monkeypatch.setattr(alpha_jobs, "TelegramAlphaService", lambda settings: telegram)
    result = await alpha_jobs.send_alpha_watchlist_digest()

    assert result == {"watchlist": 1, "sent": 1}
    assert "WatchToken" in telegram.messages[0]
    assert "MonitorToken" not in telegram.messages[0]


class FakeProviderClient:
    def __init__(self, responses):
        self.responses = responses

    async def request_json(self, method, path, **kwargs):
        value = self.responses[path]
        if isinstance(value, Exception):
            raise value
        return value

    async def close(self):
        return None


async def test_dexscreener_service_normalizes_solana_pair_data():
    client = FakeProviderClient(
        {
            "/token-pairs/v1/solana/TokenMint": [
                {
                    "chainId": "solana",
                    "pairAddress": "PairMint",
                    "dexId": "meteora",
                    "baseToken": {"address": "TokenMint", "symbol": "TOK", "name": "Token"},
                    "liquidity": {"usd": "42000"},
                    "marketCap": "180000",
                    "fdv": "250000",
                    "priceUsd": "0.000012",
                    "volume": {"h24": "95000", "h1": "12000", "m5": "1800"},
                    "txns": {"h24": {"buys": 90, "sells": 20}, "h1": {"buys": 42, "sells": 17}, "m5": {"buys": 8, "sells": 3}},
                    "pairCreatedAt": 1783440000000,
                }
            ]
        }
    )

    pairs = await DexScreenerService(Settings(), client=client).get_token_pairs("TokenMint")

    assert pairs[0].token_address == "TokenMint"
    assert pairs[0].source == "DEXSCREENER"
    assert pairs[0].fdv_usd == 250000
    assert pairs[0].volume_usd_5m == 1800
    assert pairs[0].txns_5m.buys == 8


async def test_birdeye_missing_api_key_fallback_does_not_crash():
    data = await BirdeyeService(Settings(birdeye_api_key=None)).enrich("TokenMint")

    assert data["_source"] == "Birdeye"
    assert data["holder_count"] is None


async def test_helius_missing_api_key_fallback_does_not_crash():
    data = await HeliusService(Settings(helius_api_key=None)).enrich("TokenMint")

    assert data["_source"] == "Helius"
    assert data["_snapshot"].provider == "HELIUS"


async def test_solana_rpc_fallback_normalizes_authority_and_holder_data():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json_loads(request.content)
        method = body["method"]
        if method == "getTokenSupply":
            return httpx.Response(200, json={"result": {"value": {"uiAmount": 1000}}})
        if method == "getTokenLargestAccounts":
            return httpx.Response(200, json={"result": {"value": [{"uiAmount": 100}, {"uiAmount": 50}]}})
        return httpx.Response(
            200,
            json={
                "result": {
                    "value": {
                        "data": {
                            "parsed": {
                                "info": {
                                    "mintAuthority": None,
                                    "freezeAuthority": "FreezeAuth",
                                }
                            }
                        }
                    }
                }
            },
        )

    client = httpx.AsyncClient(base_url="https://rpc.test", transport=httpx.MockTransport(handler))
    data = await SolanaRPCService(Settings(), client=client).enrich("TokenMint")

    assert data["top10_holder_percent"] == 15
    assert data["mint_authority_active"] is False
    assert data["freeze_authority_active"] is True
    await client.aclose()


async def test_launch_detector_dedupes_and_ignores_recently_scanned_tokens(db_session):
    db_session.add(
        AlphaScannedToken(
            token_address="AlreadyScanned",
            pair_address="PairOld",
            source="test",
            buys=1,
            sells=1,
            final_score=1,
            decision="IGNORE",
            should_alert=False,
            rejection_reasons=[],
            agent_scores={},
        )
    )
    await db_session.commit()

    detector = LaunchDetectorAgent(
        FakeMarketData(
            [
                _launch(token_address="AlreadyScanned"),
                _launch(token_address="FreshToken"),
                _launch(token_address="FreshToken", pair_address="OtherPair"),
            ]
        )
    )

    launches = await detector.detect(db_session, Settings())

    assert [launch.token_address for launch in launches] == ["FreshToken"]
