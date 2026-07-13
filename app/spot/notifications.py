from __future__ import annotations

from app.core.config import Settings
from app.spot.types import TradePlan
from app.telegram.client import TelegramClient


def format_trade_plan(plan: TradePlan) -> str:
    token = plan.token
    return (
        "SOLANA SPOT SETUP - PAPER TRADE\n\n"
        f"Token: ${token.symbol}\n"
        f"Address: {token.address}\n"
        "Strategy: Trend-Aligned Volatility Expansion\n"
        f"Quality: {plan.quality_score:.0f}/100\n"
        f"Regime: {plan.regime.value}\n\n"
        "Entry zone:\n"
        f"${plan.entry_low:.8f} - ${plan.entry_high:.8f}\n\n"
        f"Reference entry: ${plan.reference_entry:.8f}\n"
        f"Stop loss: ${plan.stop_loss:.8f}\n\n"
        "Targets:\n"
        f"TP1: ${plan.targets[0]:.8f}\n"
        f"TP2: ${plan.targets[1]:.8f}\n"
        f"TP3: ${plan.targets[2]:.8f}\n\n"
        f"Primary reward/risk: {plan.reward_risk:.2f}R\n"
        f"Expectancy estimate: {plan.expectancy_r:.2f}R\n\n"
        "Why it qualified:\n"
        + "\n".join(f"- {reason}" for reason in plan.reasons)
        + "\n\nMain risks:\n"
        + "\n".join(f"- {risk}" for risk in plan.risks)
        + "\n\nMode:\nPAPER TRADE / ALERT ONLY\nNo live order has been placed."
    )


def format_operational_alert(event: str, status: str, details: dict[str, object] | None = None) -> str:
    safe_details = details or {}
    lines = [
        "SOLANA ENGINE OPERATIONAL ALERT",
        "",
        f"Event: {event}",
        f"Status: {status}",
        "Mode: PAPER OBSERVATION",
        "Live trading: Disabled",
    ]
    for key, value in safe_details.items():
        if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower() or "url" in key.lower():
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


class SignalNotificationService:
    def __init__(self, settings: Settings, client: TelegramClient | None = None) -> None:
        self.settings = settings
        self.client = client or (TelegramClient(settings.telegram_bot_token) if settings.telegram_bot_token else None)

    async def send_signal(self, plan: TradePlan) -> bool:
        if not self.settings.telegram_signals_enabled or not self.client or not self.settings.telegram_chat_id:
            return False
        await self.client.send_message(self.settings.telegram_chat_id, format_trade_plan(plan), parse_mode="")
        return True

    async def send_test_message(self) -> bool:
        if not self.client or not self.settings.telegram_chat_id:
            return False
        await self.client.send_message(
            self.settings.telegram_chat_id,
            "Nexora Spot Momentum test message. No trade signal. No live order.",
            parse_mode="",
        )
        return True

    async def send_operational_alert(self, event: str, status: str, details: dict[str, object] | None = None) -> bool:
        if not self.client or not self.settings.telegram_chat_id:
            return False
        await self.client.send_message(
            self.settings.telegram_chat_id,
            format_operational_alert(event, status, details),
            parse_mode="",
        )
        return True

    async def close(self) -> None:
        if self.client:
            await self.client.close()
