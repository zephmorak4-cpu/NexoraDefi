from __future__ import annotations

from app.alpha_discovery.types import DecisionResult, RiskScore, SmartMoneyScore, TokenLaunch


def usd(value: float | None) -> str:
    return "unknown" if value is None else f"${value:,.0f}"


def format_alpha_alert(
    token: TokenLaunch,
    decision: DecisionResult,
    risk: RiskScore,
    smart_money: SmartMoneyScore,
) -> str:
    buys = token.txns.buys
    sells = max(token.txns.sells, 1)
    ratio = buys / sells
    reasons = "\n".join(f"- {item}" for item in decision.reasons[:8])
    pair_line = f"*Pair Address:* `{token.pair_address}`" if token.pair_address else "*Pair Address:* unknown"
    return "\n".join(
        [
            "*ALPHA ALERT - SOLANA NEW LAUNCH*",
            "Plain-English wallet/token intelligence summary.",
            "",
            f"*Token:* ${token.symbol or 'UNKNOWN'}",
            f"*Name:* {token.name or 'Unknown'}",
            f"*Token Address:* `{token.token_address}`",
            pair_line,
            f"*Overall Alpha Score:* {decision.final_score}/100",
            f"*Decision:* {decision.decision} - high score means stronger early-launch evidence.",
            f"*Risk Level:* {risk.risk_level}",
            "",
            f"*Liquidity:* {usd(token.liquidity_usd)}",
            f"*Market Cap:* {usd(token.market_cap_usd)}",
            f"*Volume:* {usd(token.volume_usd)}",
            f"*Buy/Sell Ratio:* {ratio:.2f}",
            f"*Smart Wallets:* {smart_money.smart_wallets_detected} detected",
            "",
            "*Why the engine flagged it:*",
            reasons,
            "",
            "*Action:* Alert only. No auto-buying. Review manually before taking action.",
        ]
    )
