import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_development_allows_missing_secrets():
    settings = Settings(app_env="development", database_url="sqlite+aiosqlite:///:memory:")
    assert settings.app_env == "development"


def test_production_requires_core_mvp_secrets(monkeypatch):
    for name in (
        "ETHERSCAN_API_KEY",
        "MORALIS_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(
        ValidationError,
        match="BLOCKCHAIN_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID",
    ):
        Settings(app_env="production", database_url="postgresql+asyncpg://localhost/db")


def test_production_requires_core_mvp_secrets_only():
    settings = Settings(
        app_env="production",
        database_url="postgresql+asyncpg://localhost/db",
        moralis_api_key="moralis",
        telegram_bot_token="telegram",
        telegram_chat_id=123,
    )

    assert settings.app_env == "production"


def test_plain_postgres_url_is_adapted():
    settings = Settings(database_url="postgresql://localhost/db")
    assert settings.sqlalchemy_database_url == "postgresql+asyncpg://localhost/db"


def test_csv_environment_values(monkeypatch):
    monkeypatch.setenv("TRACKED_COINS", "bitcoin,ethereum")
    assert Settings().tracked_coins == ["bitcoin", "ethereum"]


def test_smart_money_weights_are_configurable():
    settings = Settings(
        smart_money_profitability_weight=1,
        smart_money_consistency_weight=0,
        smart_money_risk_management_weight=0,
        smart_money_experience_weight=0,
        smart_money_recent_performance_weight=0,
    )
    assert settings.smart_money_weights["profitability"] == 1


def test_opportunity_weights_are_configurable():
    settings = Settings(
        opportunity_smart_money_weight=1,
        opportunity_adoption_weight=0,
        opportunity_growth_weight=0,
        opportunity_liquidity_weight=0,
        opportunity_momentum_weight=0,
    )
    assert settings.opportunity_weights["smart_money"] == 1


def test_risk_weights_are_configurable():
    settings = Settings(
        risk_holder_distribution_weight=1,
        risk_liquidity_stability_weight=0,
        risk_volatility_weight=0,
        risk_project_age_weight=0,
        risk_smart_money_behavior_weight=0,
        risk_contract_security_weight=0,
    )
    assert settings.risk_weights["holder_distribution"] == 1


def test_risk_thresholds_must_be_ordered():
    with pytest.raises(ValidationError, match="Risk thresholds"):
        Settings(risk_low_threshold=50, risk_medium_threshold=60)


def test_historical_feature_weights_are_configurable():
    settings = Settings(
        historical_feature_growth_weight=1,
        historical_feature_momentum_weight=0,
        historical_feature_liquidity_weight=0,
        historical_feature_risk_weight=0,
        historical_feature_smart_money_weight=0,
        historical_feature_social_weight=0,
        historical_feature_market_weight=0,
    )
    assert settings.historical_feature_weights["growth"] == 1


def test_historical_similarity_threshold_must_be_bounded():
    with pytest.raises(ValidationError, match="Historical minimum similarity"):
        Settings(historical_min_similarity_score=101)


def test_market_context_weights_are_configurable():
    settings = Settings(
        market_btc_weight=1,
        market_eth_weight=0,
        market_strength_weight=0,
        market_volatility_weight=0,
        market_capital_flow_weight=0,
        market_risk_appetite_weight=0,
    )
    assert settings.market_context_weights["btc"] == 1


def test_position_market_context_weights_are_configurable():
    settings = Settings(
        market_context_liquidity_weight=1,
        market_context_market_cap_weight=0,
        market_context_volume_trend_weight=0,
        market_context_holder_growth_weight=0,
        market_context_consensus_weight=0,
        market_context_token_age_weight=0,
        market_context_market_structure_weight=0,
    )
    assert settings.position_market_context_weights["liquidity"] == 1


def test_market_context_thresholds_must_be_ordered():
    with pytest.raises(ValidationError, match="Market sentiment thresholds"):
        Settings(market_fear_threshold=70, market_greed_threshold=60)


def test_decision_weights_are_configurable():
    settings = Settings(
        decision_smart_money_weight=1,
        decision_growth_weight=0,
        decision_momentum_weight=0,
        decision_historical_pattern_weight=0,
        decision_risk_weight=0,
        decision_market_context_weight=0,
    )
    assert settings.decision_weights["smart_money"] == 1


def test_decision_thresholds_must_be_ordered():
    with pytest.raises(ValidationError, match="Decision thresholds"):
        Settings(decision_exceptional_threshold=80, decision_very_strong_threshold=90)


def test_analyst_template_provider_is_default():
    settings = Settings()
    assert settings.analyst_provider == "template"
    assert settings.analyst_default_language == "en"


def test_remote_analyst_provider_requires_base_url():
    with pytest.raises(ValidationError, match="Analyst provider base URL"):
        Settings(analyst_provider="ollama")


def test_openai_analyst_provider_requires_api_key():
    with pytest.raises(ValidationError, match="OpenAI API key"):
        Settings(analyst_provider="openai")


def test_validation_settings_are_configurable():
    settings = Settings(validation_model_version="decision_v2", drift_alert_threshold=25)
    assert settings.validation_model_version == "decision_v2"
    assert settings.drift_alert_threshold == 25
