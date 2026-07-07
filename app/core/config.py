from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    app_name: str = "Nexora DeFi Data Infrastructure"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./nexora.db"

    etherscan_api_key: str | None = None
    moralis_api_key: str | None = None
    coingecko_api_key: str | None = None
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    cryptopanic_api_key: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: int | None = None

    etherscan_chain_id: int = 1
    moralis_chain: str = "solana"
    tracked_wallets: Annotated[list[str], NoDecode] = Field(default_factory=list)
    tracked_coins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["solana"])
    reddit_subreddits: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["cryptocurrency", "bitcoin", "ethereum"]
    )

    blockchain_refresh_seconds: int = 60
    market_refresh_seconds: int = 300
    social_refresh_seconds: int = 900
    news_refresh_seconds: int = 1800
    http_timeout_seconds: float = 15.0
    http_max_retries: int = 3
    scheduler_enabled: bool = True

    smart_money_profitability_weight: float = 0.40
    smart_money_consistency_weight: float = 0.25
    smart_money_risk_management_weight: float = 0.15
    smart_money_experience_weight: float = 0.10
    smart_money_recent_performance_weight: float = 0.10
    smart_money_elite_threshold: float = 90
    smart_money_advanced_threshold: float = 75
    smart_money_intermediate_threshold: float = 60
    smart_money_speculative_threshold: float = 40
    smart_money_qualified_threshold: float = 75
    wallet_analysis_interval_seconds: int = 86400
    wallet_scoring_interval_seconds: int = 86400
    wallet_auto_track_threshold: float = 75
    wallet_auto_track_limit: int = 100
    wallet_monitor_interval_seconds: int = 120
    wallet_monitor_transfer_limit: int = 50
    wallet_reputation_interval_seconds: int = 3600
    token_quality_interval_seconds: int = 3600
    daily_performance_report_interval_seconds: int = 86400
    smart_money_signal_interval_seconds: int = 300
    wallet_analysis_batch_size: int = 500
    candidate_discovery_interval_seconds: int = 300
    candidate_scoring_interval_seconds: int = 3600
    candidate_promotion_interval_seconds: int = 86400
    elite_demotion_interval_seconds: int = 604800
    discovery_token_scan_limit: int = 3
    discovery_transfer_limit: int = 3
    discovery_min_usd_value: float = 1000
    discovery_blacklisted_wallets: Annotated[list[str], NoDecode] = Field(default_factory=list)
    candidate_history_signature_limit: int = 1000
    candidate_live_ingestion_enabled: bool = True
    candidate_pipeline_batch_size: int = 10
    position_reconstruction_interval_seconds: int = 3600
    candidate_transaction_size_weight: float = 0.25
    candidate_consistency_weight: float = 0.20
    candidate_early_entry_weight: float = 0.20
    candidate_token_quality_weight: float = 0.15
    candidate_holding_behaviour_weight: float = 0.10
    candidate_network_influence_weight: float = 0.10
    candidate_observation_days: int = 7
    candidate_promotion_score: float = 85
    candidate_promotion_reputation: float = 85
    candidate_historical_accuracy_threshold: float = 70
    candidate_max_suspicious_score: float = 20
    candidate_demotion_reputation: float = 65
    smart_money_monitor_window_minutes: int = 10
    smart_money_cluster_window_hours: int = 24
    smart_money_cluster_min_wallets: int = 3
    smart_money_accumulation_window_hours: int = 24
    smart_money_accumulation_percentage: float = 25
    smart_money_exit_percentage: float = 50
    smart_money_entry_size_multiplier: float = 1.5

    opportunity_smart_money_weight: float = 0.30
    opportunity_adoption_weight: float = 0.25
    opportunity_growth_weight: float = 0.20
    opportunity_liquidity_weight: float = 0.15
    opportunity_momentum_weight: float = 0.10
    opportunity_exceptional_threshold: float = 90
    opportunity_strong_threshold: float = 75
    opportunity_watchlist_threshold: float = 60
    token_rapid_change_interval_seconds: int = 300
    token_growth_interval_seconds: int = 1800
    token_momentum_interval_seconds: int = 1800
    opportunity_signal_interval_seconds: int = 3600
    token_intelligence_batch_size: int = 500
    opportunity_smart_money_lookback_hours: int = 24
    momentum_overheated_24h_threshold: float = 25
    momentum_overheated_7d_threshold: float = 75
    momentum_volume_spike_threshold: float = 300
    momentum_volatility_overheated_threshold: float = 80

    risk_holder_distribution_weight: float = 0.25
    risk_liquidity_stability_weight: float = 0.20
    risk_volatility_weight: float = 0.15
    risk_project_age_weight: float = 0.10
    risk_smart_money_behavior_weight: float = 0.20
    risk_contract_security_weight: float = 0.10
    risk_low_threshold: float = 80
    risk_medium_threshold: float = 60
    risk_volatility_interval_seconds: int = 900
    risk_score_interval_seconds: int = 3600
    risk_event_interval_seconds: int = 300
    risk_batch_size: int = 500
    risk_top10_holder_warning_percentage: float = 60
    risk_top20_holder_warning_percentage: float = 80
    risk_liquidity_drop_warning_percentage: float = -30
    risk_extreme_volatility_threshold: float = 80
    risk_smart_money_exit_wallet_threshold: int = 2
    risk_smart_money_exit_lookback_hours: int = 24

    historical_snapshot_interval_seconds: int = 3600
    historical_similarity_interval_seconds: int = 86400
    historical_pattern_update_interval_seconds: int = 86400
    historical_winner_rebuild_interval_seconds: int = 604800
    historical_batch_size: int = 500
    historical_min_similarity_score: float = 60
    historical_pattern_confidence_threshold: float = 60
    historical_feature_growth_weight: float = 0.20
    historical_feature_momentum_weight: float = 0.15
    historical_feature_liquidity_weight: float = 0.15
    historical_feature_risk_weight: float = 0.15
    historical_feature_smart_money_weight: float = 0.15
    historical_feature_social_weight: float = 0.10
    historical_feature_market_weight: float = 0.10

    market_score_interval_seconds: int = 900
    sector_rotation_interval_seconds: int = 3600
    market_sentiment_interval_seconds: int = 3600
    market_context_batch_size: int = 500
    market_btc_weight: float = 0.20
    market_eth_weight: float = 0.15
    market_strength_weight: float = 0.20
    market_volatility_weight: float = 0.15
    market_capital_flow_weight: float = 0.15
    market_risk_appetite_weight: float = 0.15
    market_extreme_greed_threshold: float = 85
    market_greed_threshold: float = 65
    market_fear_threshold: float = 35
    market_strong_bull_threshold: float = 85
    market_bull_threshold: float = 75
    market_recovery_threshold: float = 60
    market_correction_threshold: float = 40
    market_bear_threshold: float = 25

    decision_generation_interval_seconds: int = 3600
    confidence_calibration_interval_seconds: int = 86400
    portfolio_statistics_interval_seconds: int = 604800
    decision_batch_size: int = 500
    decision_smart_money_weight: float = 0.25
    decision_growth_weight: float = 0.20
    decision_momentum_weight: float = 0.15
    decision_historical_pattern_weight: float = 0.20
    decision_risk_weight: float = 0.10
    decision_market_context_weight: float = 0.10
    decision_exceptional_threshold: float = 95
    decision_very_strong_threshold: float = 90
    decision_strong_threshold: float = 80
    decision_good_threshold: float = 70
    decision_watchlist_threshold: float = 60
    decision_max_position_size_percentage: float = 10
    decision_max_speculative_position_percentage: float = 2
    decision_max_token_exposure_percentage: float = 15
    decision_max_sector_exposure_percentage: float = 30

    analyst_provider: Literal["template", "ollama", "openai", "openai_compatible"] = "template"
    analyst_model: str = "nexora-template-v1"
    openai_api_key: str | None = None
    analyst_base_url: str | None = None
    analyst_api_key: str | None = None
    analyst_default_format: Literal["markdown", "plain", "telegram"] = "markdown"
    analyst_default_language: str = "en"
    analyst_report_interval_seconds: int = 3600
    analyst_market_brief_interval_seconds: int = 86400
    analyst_batch_size: int = 500
    telegram_alert_interval_seconds: int = 300
    telegram_daily_summary_interval_seconds: int = 86400

    validation_outcome_interval_seconds: int = 86400
    performance_metrics_interval_seconds: int = 86400
    validation_calibration_interval_seconds: int = 604800
    drift_detection_interval_seconds: int = 604800
    weight_optimization_interval_seconds: int = 604800
    full_backtest_interval_seconds: int = 2592000
    validation_batch_size: int = 500
    validation_model_version: str = "decision_v1"
    validation_win_return_threshold: float = 0
    drift_alert_threshold: float = 30
    calibration_error_alert_threshold: float = 20

    @field_validator("tracked_wallets", "tracked_coins", "reddit_subreddits", "discovery_blacklisted_wallets", mode="before")
    @classmethod
    def parse_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator(
        "blockchain_refresh_seconds",
        "market_refresh_seconds",
        "social_refresh_seconds",
        "news_refresh_seconds",
        "wallet_analysis_interval_seconds",
        "wallet_scoring_interval_seconds",
        "wallet_monitor_interval_seconds",
        "wallet_monitor_transfer_limit",
        "wallet_reputation_interval_seconds",
        "token_quality_interval_seconds",
        "daily_performance_report_interval_seconds",
        "wallet_auto_track_limit",
        "smart_money_signal_interval_seconds",
        "wallet_analysis_batch_size",
        "candidate_discovery_interval_seconds",
        "candidate_scoring_interval_seconds",
        "candidate_promotion_interval_seconds",
        "elite_demotion_interval_seconds",
        "discovery_token_scan_limit",
        "discovery_transfer_limit",
        "candidate_observation_days",
        "smart_money_monitor_window_minutes",
        "smart_money_cluster_window_hours",
        "smart_money_cluster_min_wallets",
        "smart_money_accumulation_window_hours",
        "token_rapid_change_interval_seconds",
        "token_growth_interval_seconds",
        "token_momentum_interval_seconds",
        "opportunity_signal_interval_seconds",
        "token_intelligence_batch_size",
        "opportunity_smart_money_lookback_hours",
        "risk_volatility_interval_seconds",
        "risk_score_interval_seconds",
        "risk_event_interval_seconds",
        "risk_batch_size",
        "risk_smart_money_exit_wallet_threshold",
        "risk_smart_money_exit_lookback_hours",
        "historical_snapshot_interval_seconds",
        "historical_similarity_interval_seconds",
        "historical_pattern_update_interval_seconds",
        "historical_winner_rebuild_interval_seconds",
        "historical_batch_size",
        "market_score_interval_seconds",
        "sector_rotation_interval_seconds",
        "market_sentiment_interval_seconds",
        "market_context_batch_size",
        "decision_generation_interval_seconds",
        "confidence_calibration_interval_seconds",
        "portfolio_statistics_interval_seconds",
        "decision_batch_size",
        "analyst_report_interval_seconds",
        "analyst_market_brief_interval_seconds",
        "analyst_batch_size",
        "telegram_alert_interval_seconds",
        "telegram_daily_summary_interval_seconds",
        "validation_outcome_interval_seconds",
        "performance_metrics_interval_seconds",
        "validation_calibration_interval_seconds",
        "drift_detection_interval_seconds",
        "weight_optimization_interval_seconds",
        "full_backtest_interval_seconds",
        "validation_batch_size",
    )
    @classmethod
    def positive_interval(cls, value: int) -> int:
        if value < 1:
            raise ValueError("scheduler intervals must be positive")
        return value

    @model_validator(mode="after")
    def validate_smart_money_configuration(self) -> "Settings":
        weights = self.smart_money_weights
        if any(weight < 0 for weight in weights.values()) or sum(weights.values()) <= 0:
            raise ValueError("Smart Money weights must be non-negative with a positive total")
        thresholds = (
            self.smart_money_elite_threshold,
            self.smart_money_advanced_threshold,
            self.smart_money_intermediate_threshold,
            self.smart_money_speculative_threshold,
        )
        if not all(0 <= value <= 100 for value in thresholds) or not all(
            left > right for left, right in zip(thresholds, thresholds[1:])
        ):
            raise ValueError("Smart Money tier thresholds must descend within 0-100")
        return self

    @model_validator(mode="after")
    def validate_candidate_discovery_configuration(self) -> "Settings":
        weights = self.candidate_score_weights
        if any(weight < 0 for weight in weights.values()) or sum(weights.values()) <= 0:
            raise ValueError("Candidate score weights must be non-negative with a positive total")
        bounded = (
            self.candidate_promotion_score,
            self.candidate_promotion_reputation,
            self.candidate_historical_accuracy_threshold,
            self.candidate_max_suspicious_score,
            self.candidate_demotion_reputation,
        )
        if not all(0 <= value <= 100 for value in bounded):
            raise ValueError("Candidate discovery thresholds must be within 0-100")
        return self

    @model_validator(mode="after")
    def validate_opportunity_configuration(self) -> "Settings":
        weights = self.opportunity_weights
        if any(weight < 0 for weight in weights.values()) or sum(weights.values()) <= 0:
            raise ValueError("Opportunity weights must be non-negative with a positive total")
        thresholds = (
            self.opportunity_exceptional_threshold,
            self.opportunity_strong_threshold,
            self.opportunity_watchlist_threshold,
        )
        if not all(0 <= value <= 100 for value in thresholds) or not all(
            left > right for left, right in zip(thresholds, thresholds[1:])
        ):
            raise ValueError("Opportunity thresholds must descend within 0-100")
        return self

    @model_validator(mode="after")
    def validate_risk_configuration(self) -> "Settings":
        weights = self.risk_weights
        if any(weight < 0 for weight in weights.values()) or sum(weights.values()) <= 0:
            raise ValueError("Risk weights must be non-negative with a positive total")
        if not 0 <= self.risk_medium_threshold < self.risk_low_threshold <= 100:
            raise ValueError("Risk thresholds must be ordered within 0-100")
        bounded = (
            self.risk_top10_holder_warning_percentage,
            self.risk_top20_holder_warning_percentage,
            self.risk_extreme_volatility_threshold,
        )
        if not all(0 <= value <= 100 for value in bounded):
            raise ValueError("Risk warning thresholds must be within 0-100")
        return self

    @model_validator(mode="after")
    def validate_historical_configuration(self) -> "Settings":
        weights = self.historical_feature_weights
        if any(weight < 0 for weight in weights.values()) or sum(weights.values()) <= 0:
            raise ValueError("Historical feature weights must be non-negative with a positive total")
        if not 0 <= self.historical_min_similarity_score <= 100:
            raise ValueError("Historical minimum similarity score must be within 0-100")
        if not 0 <= self.historical_pattern_confidence_threshold <= 100:
            raise ValueError("Historical pattern confidence threshold must be within 0-100")
        return self

    @model_validator(mode="after")
    def validate_market_context_configuration(self) -> "Settings":
        weights = self.market_context_weights
        if any(weight < 0 for weight in weights.values()) or sum(weights.values()) <= 0:
            raise ValueError("Market context weights must be non-negative with a positive total")
        sentiment = (
            self.market_fear_threshold,
            self.market_greed_threshold,
            self.market_extreme_greed_threshold,
        )
        if not all(0 <= value <= 100 for value in sentiment) or not all(
            left < right for left, right in zip(sentiment, sentiment[1:])
        ):
            raise ValueError("Market sentiment thresholds must ascend within 0-100")
        phases = (
            self.market_strong_bull_threshold,
            self.market_bull_threshold,
            self.market_recovery_threshold,
            self.market_correction_threshold,
            self.market_bear_threshold,
        )
        if not all(0 <= value <= 100 for value in phases) or not all(
            left > right for left, right in zip(phases, phases[1:])
        ):
            raise ValueError("Market phase thresholds must descend within 0-100")
        return self

    @model_validator(mode="after")
    def validate_decision_configuration(self) -> "Settings":
        weights = self.decision_weights
        if any(weight < 0 for weight in weights.values()) or sum(weights.values()) <= 0:
            raise ValueError("Decision weights must be non-negative with a positive total")
        thresholds = (
            self.decision_exceptional_threshold,
            self.decision_very_strong_threshold,
            self.decision_strong_threshold,
            self.decision_good_threshold,
            self.decision_watchlist_threshold,
        )
        if not all(0 <= value <= 100 for value in thresholds) or not all(
            left > right for left, right in zip(thresholds, thresholds[1:])
        ):
            raise ValueError("Decision thresholds must descend within 0-100")
        exposure = (
            self.decision_max_position_size_percentage,
            self.decision_max_speculative_position_percentage,
            self.decision_max_token_exposure_percentage,
            self.decision_max_sector_exposure_percentage,
        )
        if not all(0 <= value <= 100 for value in exposure):
            raise ValueError("Decision exposure limits must be within 0-100")
        return self

    @model_validator(mode="after")
    def validate_analyst_configuration(self) -> "Settings":
        if self.analyst_provider == "openai" and not self.openai_api_key:
            raise ValueError("OpenAI API key is required for the OpenAI analyst provider")
        if self.analyst_provider in {"ollama", "openai_compatible"} and not self.analyst_base_url:
            raise ValueError("Analyst provider base URL is required for remote providers")
        return self

    @model_validator(mode="after")
    def require_production_secrets(self) -> "Settings":
        if self.app_env != "production":
            return self
        required = {
            "DATABASE_URL": self.database_url if self.database_url.startswith(("postgresql+asyncpg://", "postgresql://")) else None,
            "BLOCKCHAIN_API_KEY": self.moralis_api_key,
            "TELEGRAM_BOT_TOKEN": self.telegram_bot_token,
            "TELEGRAM_CHAT_ID": self.telegram_chat_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"missing production environment variables: {', '.join(missing)}")
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url

    @property
    def smart_money_weights(self) -> dict[str, float]:
        return {
            "profitability": self.smart_money_profitability_weight,
            "consistency": self.smart_money_consistency_weight,
            "risk_management": self.smart_money_risk_management_weight,
            "experience": self.smart_money_experience_weight,
            "recent_performance": self.smart_money_recent_performance_weight,
        }

    @property
    def candidate_score_weights(self) -> dict[str, float]:
        return {
            "transaction_size": self.candidate_transaction_size_weight,
            "consistency": self.candidate_consistency_weight,
            "early_entry": self.candidate_early_entry_weight,
            "token_quality": self.candidate_token_quality_weight,
            "holding_behaviour": self.candidate_holding_behaviour_weight,
            "network_influence": self.candidate_network_influence_weight,
        }

    @property
    def opportunity_weights(self) -> dict[str, float]:
        return {
            "smart_money": self.opportunity_smart_money_weight,
            "adoption": self.opportunity_adoption_weight,
            "growth": self.opportunity_growth_weight,
            "liquidity": self.opportunity_liquidity_weight,
            "momentum": self.opportunity_momentum_weight,
        }

    @property
    def risk_weights(self) -> dict[str, float]:
        return {
            "holder_distribution": self.risk_holder_distribution_weight,
            "liquidity_stability": self.risk_liquidity_stability_weight,
            "volatility": self.risk_volatility_weight,
            "project_age": self.risk_project_age_weight,
            "smart_money_behavior": self.risk_smart_money_behavior_weight,
            "contract_security": self.risk_contract_security_weight,
        }

    @property
    def historical_feature_weights(self) -> dict[str, float]:
        return {
            "growth": self.historical_feature_growth_weight,
            "momentum": self.historical_feature_momentum_weight,
            "liquidity": self.historical_feature_liquidity_weight,
            "risk": self.historical_feature_risk_weight,
            "smart_money": self.historical_feature_smart_money_weight,
            "social": self.historical_feature_social_weight,
            "market": self.historical_feature_market_weight,
        }

    @property
    def market_context_weights(self) -> dict[str, float]:
        return {
            "btc": self.market_btc_weight,
            "eth": self.market_eth_weight,
            "market_strength": self.market_strength_weight,
            "market_volatility": self.market_volatility_weight,
            "capital_flow": self.market_capital_flow_weight,
            "risk_appetite": self.market_risk_appetite_weight,
        }

    @property
    def decision_weights(self) -> dict[str, float]:
        return {
            "smart_money": self.decision_smart_money_weight,
            "growth": self.decision_growth_weight,
            "momentum": self.decision_momentum_weight,
            "historical_pattern": self.decision_historical_pattern_weight,
            "risk": self.decision_risk_weight,
            "market_context": self.decision_market_context_weight,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
