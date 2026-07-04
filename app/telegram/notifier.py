from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.analyst_engine import AnalystEngine
from app.core.config import Settings
from app.core.logging import get_logger
from app.models import Alert, SmartMoneySignal, Token
from app.telegram.client import TelegramClient

logger = get_logger(__name__)


class TelegramNotifier:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        client: TelegramClient | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.client = client

    def configured(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    def _client(self) -> TelegramClient:
        if self.client is None:
            self.client = TelegramClient(self.settings.telegram_bot_token or "")
        return self.client

    async def send_recent_smart_money_alerts(self, since: datetime | None = None, limit: int = 10) -> int:
        if not self.configured():
            logger.info("telegram_skipped", reason="missing_token_or_chat_id")
            return 0
        since = since or datetime.now(timezone.utc) - timedelta(seconds=self.settings.telegram_alert_interval_seconds)
        solana_alerts = list(
            (
                await self.session.scalars(
                    select(Alert)
                    .where(Alert.created_at >= since, Alert.alert_type.like("solana:%"))
                    .order_by(Alert.created_at.desc(), Alert.id.desc())
                    .limit(limit)
                )
            ).all()
        )
        sent = 0
        for alert in solana_alerts:
            await self._client().send_message(self.settings.telegram_chat_id or 0, alert.message)
            sent += 1
        if sent:
            logger.info("telegram_solana_smart_money_alerts_sent", alerts=sent)
            return sent

        signals = list(
            (
                await self.session.scalars(
                    select(SmartMoneySignal)
                    .where(SmartMoneySignal.created_at >= since)
                    .order_by(SmartMoneySignal.created_at.desc(), SmartMoneySignal.id.desc())
                    .limit(limit)
                )
            ).all()
        )
        engine = AnalystEngine(self.session, self.settings)
        for signal in signals:
            report = await engine.token_report(signal.token_id, output_format="telegram")
            await self._client().send_message(self.settings.telegram_chat_id or 0, report.content)
            sent += 1
        logger.info("telegram_smart_money_alerts_sent", alerts=sent)
        return sent

    async def send_daily_summary(self, now: datetime | None = None, limit: int = 10) -> int:
        if not self.configured():
            logger.info("telegram_skipped", reason="missing_token_or_chat_id")
            return 0
        now = now or datetime.now(timezone.utc)
        since = now - timedelta(days=1)
        rows = (
            await self.session.execute(
                select(SmartMoneySignal, Token)
                .join(Token, Token.id == SmartMoneySignal.token_id)
                .where(SmartMoneySignal.created_at >= since)
                .order_by(SmartMoneySignal.signal_strength.desc(), SmartMoneySignal.created_at.desc())
                .limit(limit)
            )
        ).all()
        if not rows:
            text = "*Daily Smart Money Summary*\nNo Smart Money signals were observed in the last 24 hours."
        else:
            lines = ["*Daily Smart Money Summary*"]
            for signal, token in rows:
                lines.append(
                    f"- {token.symbol}: {signal.signal_type}, strength {signal.signal_strength}, "
                    f"confidence {signal.confidence_score}, wallets {signal.number_of_smart_wallets}"
                )
            text = "\n".join(lines)
        await self._client().send_message(self.settings.telegram_chat_id or 0, text)
        logger.info("telegram_daily_summary_sent", signals=len(rows))
        return 1

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()
