from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Record(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class TokenRecord(Record):
    blockchain_address: str | None = None
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    chain: str = "ethereum"
    category: str | None = None


class TransactionRecord(Record):
    external_id: str
    wallet_address: str
    token: TokenRecord | None = None
    transaction_type: str
    amount: Decimal
    price: Decimal | None = None
    timestamp: datetime


class PriceRecord(Record):
    coin_id: str
    symbol: str
    name: str
    price: Decimal
    market_cap: Decimal | None = None
    volume: Decimal | None = None
    liquidity_value: Decimal | None = None
    timestamp: datetime


class SocialRecord(Record):
    coin_id: str
    symbol: str
    name: str
    source: str
    mentions: int = Field(ge=0)
    sentiment_score: Decimal | None = Field(default=None, ge=-1, le=1)
    timestamp: datetime


class NewsRecord(Record):
    external_id: str
    title: str
    url: HttpUrl
    source: str | None = None
    sentiment: str | None = None
    published_at: datetime


class WalletMetricResponse(Record):
    model_config = ConfigDict(from_attributes=True)

    total_transactions: int
    total_buys: int
    total_sells: int
    total_tokens_traded: int
    estimated_total_profit: Decimal
    estimated_roi_percentage: Decimal
    average_return_percentage: Decimal
    average_holding_time_days: Decimal
    win_rate: Decimal
    loss_rate: Decimal
    largest_winner_percentage: Decimal
    largest_loss_percentage: Decimal
    last_updated: datetime


class WalletScoreResponse(Record):
    model_config = ConfigDict(from_attributes=True)

    profitability_score: Decimal
    consistency_score: Decimal
    risk_management_score: Decimal
    experience_score: Decimal
    recent_performance_score: Decimal
    final_smart_money_score: Decimal
    wallet_tier: str
    confidence_score: Decimal
    calculated_at: datetime


class WalletPositionResponse(Record):
    model_config = ConfigDict(from_attributes=True)

    token_id: int
    total_bought_amount: Decimal
    total_sold_amount: Decimal
    current_balance: Decimal
    average_entry_price: Decimal
    realized_profit: Decimal
    unrealized_profit: Decimal
    first_purchase_date: datetime | None
    latest_activity_date: datetime


class RankedWalletResponse(Record):
    wallet_address: str
    chain: str
    score: WalletScoreResponse


class WalletProfileResponse(RankedWalletResponse):
    metrics: WalletMetricResponse | None
    positions: list[WalletPositionResponse]


class SmartMoneySignalResponse(Record):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token_id: int
    signal_type: str
    signal_strength: Decimal
    confidence_score: Decimal
    number_of_smart_wallets: int
    total_capital_moved: Decimal
    supporting_data_json: dict
    created_at: datetime


class TokenGrowthMetricResponse(Record):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token_id: int
    holder_count: int
    holder_growth_24h: Decimal
    holder_growth_7d: Decimal
    transaction_count: int
    transaction_growth_24h: Decimal
    transaction_growth_7d: Decimal
    volume_24h: Decimal | None
    volume_growth_24h: Decimal
    volume_growth_7d: Decimal
    market_cap: Decimal | None
    market_cap_growth_24h: Decimal
    market_cap_growth_7d: Decimal
    liquidity_value: Decimal | None
    liquidity_growth_24h: Decimal
    liquidity_growth_7d: Decimal
    calculated_at: datetime


class MomentumMetricResponse(Record):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token_id: int
    price_change_1h: Decimal
    price_change_24h: Decimal
    price_change_7d: Decimal
    price_change_30d: Decimal
    volatility_score: Decimal
    momentum_score: Decimal
    momentum_stage: str
    calculated_at: datetime


class SmartMoneyWatchlistResponse(Record):
    token_id: int
    symbol: str | None = None
    signal_type: str
    signal_strength: Decimal
    confidence_score: Decimal
    number_of_smart_wallets: int
    total_capital_moved: Decimal
    created_at: datetime
    risk_level: str | None = None
    overall_risk_score: Decimal | None = None
    liquidity_value: Decimal | None = None
    momentum_stage: str | None = None


class TokenRiskMetricResponse(Record):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token_id: int
    holder_concentration_score: Decimal
    liquidity_risk_score: Decimal
    volatility_risk_score: Decimal
    age_risk_score: Decimal
    smart_money_exit_risk_score: Decimal
    contract_security_score: Decimal
    overall_risk_score: Decimal
    risk_level: str
    calculated_at: datetime


class TokenRiskAnalysisResponse(TokenRiskMetricResponse):
    risk_factors: dict


class RiskEventResponse(Record):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token_id: int
    event_type: str
    severity: str
    confidence_score: Decimal
    description: str
    supporting_data_json: dict
    created_at: datetime


class AnalystReportResponse(Record):
    report_type: str
    format: str
    language: str
    content: str
    evidence: dict

