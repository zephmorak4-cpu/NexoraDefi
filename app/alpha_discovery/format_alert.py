from __future__ import annotations

from app.alpha_discovery.types import DecisionResult, RiskScore, SmartMoneyScore, TokenLaunch


def usd(value: float | None) -> str:
    return "unknown" if value is None else f"${value:,.0f}"


def text(value: object | None) -> str:
    if value in (None, ""):
        return "Unknown"
    if value is False:
        return "Disabled"
    if value is True:
        return "Active"
    return str(value)


def format_alpha_alert(
    token: TokenLaunch,
    decision: DecisionResult,
    risk: RiskScore,
    smart_money: SmartMoneyScore,
) -> str:
    buys = token.txns.buys
    sells = max(token.txns.sells, 1)
    five_min_buys = token.txns_5m.buys
    five_min_sells = token.txns_5m.sells
    ratio_source = token.txns_5m if five_min_buys or five_min_sells else token.txns
    ratio = ratio_source.buys / max(ratio_source.sells, 1)
    reasons = "\n".join(f"- {item}" for item in decision.reasons[:8])
    pair_line = f"*Pair Address:* `{token.pair_address}`" if token.pair_address else "*Pair Address:* unknown"
    sources = "\n".join(f"- {source}" for source in token.sources) or "- DEX Screener"
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
            f"*FDV:* {usd(token.fdv_usd)}",
            f"*Price:* {token.price_usd if token.price_usd is not None else 'unknown'}",
            f"*24h Volume:* {usd(token.volume_usd_24h or token.volume_usd)}",
            f"*5m Volume:* {usd(token.volume_usd_5m)}",
            f"*Buy/Sell 5m:* {five_min_buys} / {five_min_sells}",
            f"*Buy/Sell Ratio:* {ratio:.2f}",
            f"*Smart Wallets:* {smart_money.smart_wallets_detected} detected",
            f"*Holders:* {token.holder_count if token.holder_count is not None else 'unknown'}",
            f"*Top 10 Holders:* {token.top10_holder_percent:.2f}%" if token.top10_holder_percent is not None else "*Top 10 Holders:* unknown",
            f"*Mint Authority:* {text(token.mint_authority_active)}",
            f"*Freeze Authority:* {text(token.freeze_authority_active)}",
            "",
            "*Sources:*",
            sources,
            "",
            "*Why the engine flagged it:*",
            reasons,
            "",
            "*Action:* Alert only. No auto-buying. Review manually before taking action.",
        ]
    )
