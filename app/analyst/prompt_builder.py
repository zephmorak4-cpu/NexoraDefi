from __future__ import annotations

import json


class PromptBuilder:
    def build(self, report_type: str, evidence: dict, language: str = "en") -> str:
        return "\n".join([
            "You are Nexora's crypto analyst formatter.",
            "Use only the structured evidence provided.",
            "Do not invent facts, prices, wallets, risks, or recommendations.",
            "Never promise profits or guarantee returns.",
            f"Report type: {report_type}",
            f"Language: {language}",
            "Required sections: Token, Wallet Activity, Why It Matters, Risk Summary, Confidence Score, Suggested Action.",
            "Structured evidence:",
            json.dumps(evidence, default=str, sort_keys=True),
        ])
