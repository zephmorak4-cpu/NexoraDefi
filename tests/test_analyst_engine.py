from datetime import datetime, timezone

from app.analyst.analyst_engine import AnalystEngine
from app.analyst.explanation_engine import assert_safe_language
from app.analyst.prompt_builder import PromptBuilder
from app.analyst.providers import OpenAIProvider, TemplateProvider, build_provider
from app.analyst.template_engine import MANDATORY_SECTIONS, TemplateEngine
from app.core.config import Settings
from app.models import (
    MomentumMetric,
    RiskEvent,
    SmartMoneySignal,
    Token,
    TokenGrowthMetric,
    TokenRiskMetric,
)


async def seed_analyst_data(db_session):
    now = datetime.now(timezone.utc)
    token = Token(blockchain_address="0xanalyst", symbol="ANLY", name="Analyst Token", chain="ethereum", category="AI")
    db_session.add(token)
    await db_session.flush()
    db_session.add_all([
        TokenRiskMetric(
            token_id=token.id, holder_concentration_score=80, liquidity_risk_score=70,
            volatility_risk_score=75, age_risk_score=60, smart_money_exit_risk_score=90,
            contract_security_score=60, overall_risk_score=72, risk_level="MEDIUM",
            calculated_at=now,
        ),
        TokenGrowthMetric(
            token_id=token.id, holder_count=100, holder_growth_24h=20, holder_growth_7d=50,
            transaction_count=80, transaction_growth_24h=15, transaction_growth_7d=40,
            volume_growth_24h=80, volume_growth_7d=90, calculated_at=now,
        ),
        MomentumMetric(
            token_id=token.id, price_change_1h=1, price_change_24h=5,
            price_change_7d=20, price_change_30d=30,
            volatility_score=25, momentum_score=80, momentum_stage="TRENDING",
            calculated_at=now,
        ),
        SmartMoneySignal(
            token_id=token.id, signal_type="ELITE_ENTRY", signal_strength=92,
            confidence_score=90, number_of_smart_wallets=2,
            total_capital_moved=100000, supporting_data_json={},
            event_fingerprint="analyst-smart", created_at=now,
        ),
        RiskEvent(
            token_id=token.id, event_type="LIQUIDITY_WARNING",
            severity="MEDIUM", confidence_score=60,
            description="Liquidity declined in structured risk data.",
            supporting_data_json={}, created_at=now,
        ),
    ])
    await db_session.commit()
    return token


def test_prompt_and_template_generation():
    evidence = {"token": {"symbol": "ANLY"}, "latest_smart_money_signal": {"signal_type": "ELITE_ENTRY"}}
    prompt = PromptBuilder().build("smart_money_alert", evidence)
    assert "Use only the structured evidence" in prompt
    sections = {section: "Evidence-backed text." for section in MANDATORY_SECTIONS}
    report = TemplateEngine().render("smart_money_alert", sections, "telegram")
    assert "*Token*" in report.content
    assert report.format == "telegram"


async def test_template_provider_returns_fallback():
    result = await TemplateProvider(Settings()).generate("prompt", "fallback")
    assert result.content == "fallback"
    assert result.provider == "template"


def test_openai_provider_requires_key_and_can_be_selected():
    settings = Settings(analyst_provider="openai", openai_api_key="test-key", analyst_model="test-model")
    assert isinstance(build_provider(settings), OpenAIProvider)


async def test_token_report_uses_structured_evidence(db_session):
    token = await seed_analyst_data(db_session)
    report = await AnalystEngine(db_session, Settings()).token_report(token.id)
    assert report.report_type == "smart_money_alert"
    assert "Wallet Activity" in report.content
    assert "ELITE_ENTRY" in report.content
    assert report.evidence["latest_smart_money_signal"]["signal_strength"] == 92
    assert report.evidence["risk"]["risk_level"] == "MEDIUM"
    assert_safe_language(report.content)


async def test_smart_money_and_watchlist_reports(db_session):
    await seed_analyst_data(db_session)
    engine = AnalystEngine(db_session, Settings())
    smart = await engine.smart_money_report(output_format="markdown")
    watchlist = await engine.watchlist_reports(limit=5, output_format="plain")
    assert "Smart Money" in smart.content
    assert len(watchlist) == 1
    assert watchlist[0].evidence["latest_smart_money_signal"]["signal_type"] == "ELITE_ENTRY"
