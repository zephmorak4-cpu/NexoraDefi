from datetime import datetime, timezone

from app.core.config import Settings
from app.models import SmartMoneySignal, Token
from app.telegram.notifier import TelegramNotifier


class FakeTelegramClient:
    def __init__(self) -> None:
        self.messages = []

    async def send_message(self, chat_id: int, text: str, parse_mode: str = "Markdown", disable_web_page_preview: bool = True):
        self.messages.append({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        })
        return {"ok": True}

    async def close(self) -> None:
        return None


async def test_telegram_notifier_sends_recent_smart_money_alert(db_session):
    now = datetime.now(timezone.utc)
    token = Token(blockchain_address="0xtg", symbol="TG", name="Telegram Token", chain="ethereum")
    db_session.add(token)
    await db_session.flush()
    db_session.add(
        SmartMoneySignal(
            token_id=token.id,
            signal_type="ELITE_ENTRY",
            signal_strength=90,
            confidence_score=88,
            number_of_smart_wallets=2,
            total_capital_moved=1000,
            supporting_data_json={},
            event_fingerprint="telegram-alert",
            created_at=now,
        )
    )
    await db_session.commit()
    client = FakeTelegramClient()
    settings = Settings(telegram_bot_token="test-token", telegram_chat_id=12345)

    sent = await TelegramNotifier(db_session, settings, client).send_recent_smart_money_alerts(since=now)

    assert sent == 1
    assert client.messages[0]["chat_id"] == 12345
    assert "Wallet Activity" in client.messages[0]["text"]


async def test_telegram_notifier_skips_without_credentials(db_session):
    client = FakeTelegramClient()
    sent = await TelegramNotifier(db_session, Settings(), client).send_recent_smart_money_alerts()
    assert sent == 0
    assert client.messages == []
