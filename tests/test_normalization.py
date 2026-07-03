from decimal import Decimal

from app.collectors.blockchain import BlockchainCollector
from app.collectors.news import NewsCollector


def test_blockchain_token_transfer_normalization():
    item = {
        "hash": "0xabc", "logIndex": "4", "from": "0xsender", "to": "0xwallet",
        "value": "1500000", "tokenDecimal": "6", "tokenSymbol": "USDC",
        "tokenName": "USD Coin", "contractAddress": "0xtoken", "timeStamp": "1700000000",
    }
    record = BlockchainCollector.normalize_transaction(item, "0xwallet", True)
    assert record.amount == Decimal("1.5")
    assert record.transaction_type == "in"
    assert record.token.symbol == "USDC"


def test_news_sentiment_normalization():
    record = NewsCollector.normalize({
        "id": 10, "title": "Market update", "url": "https://example.com/story",
        "published_at": "2025-01-01T00:00:00Z", "source": {"title": "Example"},
        "votes": {"positive": 3, "negative": 1},
    })
    assert record.sentiment == "positive"

