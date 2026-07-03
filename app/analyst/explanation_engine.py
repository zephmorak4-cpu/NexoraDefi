from __future__ import annotations

from decimal import Decimal

FORBIDDEN_PHRASES = (
    "will definitely",
    "cannot lose",
    "guaranteed",
    "guarantee returns",
    "guaranteed returns",
)


class ExplanationEngine:
    def token_sections(self, evidence: dict) -> dict[str, str | list[str]]:
        token = evidence["token"]
        latest_signal = evidence.get("latest_smart_money_signal", {})
        return {
            "Token": f"{token.get('symbol', 'UNKNOWN')} ({token.get('name', 'unknown token')}) on {token.get('chain', 'unknown chain')}.",
            "Wallet Activity": self.wallet_activity(evidence),
            "Why It Matters": (
                "High-quality wallet activity can surface tokens before broader market attention arrives. "
                "This report summarizes only observed Smart Money, growth, momentum, and basic risk evidence."
            ),
            "Risk Summary": self.risk_summary(evidence),
            "Confidence Score": str(latest_signal.get("confidence_score", "n/a")),
            "Suggested Action": self.suggested_action(evidence),
        }

    def smart_money_sections(self, evidence: dict) -> dict[str, str | list[str]]:
        signals = evidence.get("smart_money_signals", [])
        return {
            "Token": "Multiple Smart Money token signals.",
            "Wallet Activity": [
                f"{signal['signal_type']} on token {signal['token_id']} with {signal['number_of_smart_wallets']} wallets and capital moved {signal['total_capital_moved']}"
                for signal in signals
            ],
            "Why It Matters": "Smart Money activity can indicate whether experienced wallets are entering, accumulating, clustering, or exiting.",
            "Risk Summary": "Review token-level risk before acting. Exit signals should override bullish wallet activity.",
            "Confidence Score": self.aggregate_confidence(signals),
            "Suggested Action": "Review latest Smart Money signals and add only supported tokens to the watchlist.",
        }

    @staticmethod
    def wallet_activity(evidence: dict) -> list[str]:
        signals = evidence.get("smart_money_signals", [])
        if not signals:
            return ["No Smart Money signal is available in structured evidence."]
        return [
            (
                f"{signal.get('signal_type', 'UNKNOWN')} with {signal.get('number_of_smart_wallets', 0)} smart wallets, "
                f"strength {signal.get('signal_strength', 'n/a')}, capital moved {signal.get('total_capital_moved', 'n/a')}."
            )
            for signal in signals
        ]

    @staticmethod
    def risk_summary(evidence: dict) -> str:
        risk = evidence.get("risk") or {}
        if not risk:
            return "No risk profile is available in structured evidence."
        return (
            f"Risk level is {risk.get('risk_level', 'UNKNOWN')} with score {risk.get('overall_risk_score', 'n/a')}. "
            f"Volatility risk score: {risk.get('volatility_risk_score', 'n/a')}; liquidity risk score: {risk.get('liquidity_risk_score', 'n/a')}."
        )

    @staticmethod
    def suggested_action(evidence: dict) -> str:
        signal = evidence.get("latest_smart_money_signal") or {}
        risk = evidence.get("risk") or {}
        if signal.get("signal_type") == "SMART_MONEY_EXIT":
            return "Avoid new entries and monitor exits."
        if risk.get("risk_level") == "HIGH":
            return "Keep on watchlist only until risk improves."
        if signal:
            return "Add to watchlist and wait for continued Smart Money confirmation."
        return "Wait for verified Smart Money activity."

    @staticmethod
    def aggregate_confidence(signals: list[dict]) -> str:
        if not signals:
            return "n/a"
        values = [Decimal(str(signal.get("confidence_score", 0))) for signal in signals]
        return str(sum(values, Decimal("0")) / len(values))


def assert_safe_language(content: str) -> None:
    lower = content.lower()
    found = [phrase for phrase in FORBIDDEN_PHRASES if phrase in lower]
    if found:
        raise ValueError(f"forbidden analyst language detected: {', '.join(found)}")
