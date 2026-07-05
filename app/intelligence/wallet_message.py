from __future__ import annotations

from decimal import Decimal
from typing import Any


def short_address(address: str) -> str:
    if len(address) <= 16:
        return address
    return f"{address[:6]}...{address[-6:]}"


def score(value: Any) -> str:
    return f"{Decimal(str(value)):.2f}/100"


def build_wallet_report_completed_message(export: dict[str, object]) -> str:
    summary = export["summary"]
    rankings = export["rankings"] if isinstance(export["rankings"], list) else []
    top = rankings[:5]
    lines = [
        "*Wallet Intelligence Report Completed*",
        "",
        f"*Wallets Analysed:* {summary['total_wallets']} candidate wallets",
        "*Important:* These are candidate wallets under observation. None are approved for Smart Money alerts yet.",
        "",
        "*What The Scores Mean*",
        "- Copy Performance Score: estimated quality if this wallet were copied, from 0 to 100.",
        "- Reputation Score: evidence that this wallet behaves like smart money, from 0 to 100.",
        "- Historical Accuracy: early estimate of successful behaviour, from 0 to 100.",
        "- Recommendation: AI guidance only. Admin approval is still required.",
        "",
        "*Top Candidate Wallets For Review*",
    ]
    if not top:
        lines.append("No candidate wallets are available yet.")
    for index, item in enumerate(top, start=1):
        lines.extend(
            [
                f"{index}. Candidate Wallet Address: `{item['wallet_address']}`",
                f"   Short ID: `{short_address(str(item['wallet_address']))}`",
                f"   Trading Style: {item['trading_style']}",
                f"   Copy Performance: {score(item['copy_performance_score'])}",
                f"   Reputation: {score(item['wallet_reputation_score'])}",
                f"   Historical Accuracy: {score(item['historical_accuracy'])}",
                f"   Risk: {item['risk_classification']} ({score(item['risk_score'])})",
                f"   AI Recommendation: {item['administrator_recommendation']}",
                f"   Why: {item['recommendation_reasoning']}",
                "",
            ]
        )
    if top and Decimal(str(top[0]["copy_performance_score"])) < Decimal("50"):
        lines.extend(
            [
                "*Why The Scores Look Low*",
                "The system has discovered wallets, but most still have limited observation history.",
                "Low scores do not mean the wallet is bad; they mean the system needs more evidence before approval.",
                "",
            ]
        )
    lines.extend(
        [
            "*Next Admin Action*",
            "Open `/admin/rankings` or `/admin/reports` for the full review.",
            "Manual approval required: approve only wallets you trust using `/admin/approve-wallet`.",
            "Do not treat any candidate as an elite wallet until it is manually approved.",
            "",
            f"*PDF Report:* `{export['pdf_path']}`",
        ]
    )
    return "\n".join(lines)
