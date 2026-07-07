from __future__ import annotations

from typing import Any

from app.alpha_discovery.types import ProviderSnapshot, TokenLaunch, TokenTxns
from app.alpha_discovery.utils import number


def txns(payload: dict[str, Any] | None) -> TokenTxns:
    payload = payload or {}
    return TokenTxns(buys=int(payload.get("buys") or 0), sells=int(payload.get("sells") or 0))


def normalize_dex_pair(pair: dict[str, Any], profile: dict[str, Any] | None = None) -> TokenLaunch:
    profile = profile or {}
    base = pair.get("baseToken") or {}
    liquidity = pair.get("liquidity") or {}
    volume = pair.get("volume") or {}
    pair_txns = pair.get("txns") or {}
    normalized = {
        "tokenAddress": str(base.get("address") or profile.get("tokenAddress") or ""),
        "pairAddress": pair.get("pairAddress"),
        "symbol": base.get("symbol"),
        "name": base.get("name"),
        "dex": pair.get("dexId"),
        "source": "DEXSCREENER",
        "liquidityUsd": number(liquidity.get("usd")),
        "marketCapUsd": number(pair.get("marketCap")),
        "fdvUsd": number(pair.get("fdv")),
        "priceUsd": number(pair.get("priceUsd")),
        "volumeUsd24h": number(volume.get("h24")),
        "volumeUsd1h": number(volume.get("h1")),
        "volumeUsd5m": number(volume.get("m5")),
        "txns5m": {"buys": int((pair_txns.get("m5") or {}).get("buys") or 0), "sells": int((pair_txns.get("m5") or {}).get("sells") or 0)},
        "txns1h": {"buys": int((pair_txns.get("h1") or {}).get("buys") or 0), "sells": int((pair_txns.get("h1") or {}).get("sells") or 0)},
        "pairCreatedAt": str(pair.get("pairCreatedAt")) if pair.get("pairCreatedAt") else None,
        "url": pair.get("url"),
    }
    return TokenLaunch(
        token_address=normalized["tokenAddress"],
        pair_address=normalized["pairAddress"],
        symbol=normalized["symbol"],
        name=normalized["name"],
        launch_time=normalized["pairCreatedAt"],
        dex=normalized["dex"],
        source="DEXSCREENER",
        liquidity_usd=normalized["liquidityUsd"],
        market_cap_usd=normalized["marketCapUsd"] or normalized["fdvUsd"],
        fdv_usd=normalized["fdvUsd"],
        price_usd=normalized["priceUsd"],
        volume_usd=normalized["volumeUsd24h"],
        volume_usd_24h=normalized["volumeUsd24h"],
        volume_usd_1h=normalized["volumeUsd1h"],
        volume_usd_5m=normalized["volumeUsd5m"],
        txns=txns(pair_txns.get("h24")),
        txns_1h=txns(pair_txns.get("h1")),
        txns_5m=txns(pair_txns.get("m5")),
        sources=["DEX Screener"],
        provider_snapshots=[ProviderSnapshot("DEXSCREENER", pair, normalized)],
    )


def merge_token_data(base: TokenLaunch, *updates: dict[str, Any]) -> TokenLaunch:
    values = base.__dict__.copy()
    snapshots = list(base.provider_snapshots)
    sources = list(base.sources)
    risk_flags = list(base.risk_flags)
    for update in updates:
        snapshot = update.pop("_snapshot", None)
        source = update.pop("_source", None)
        flags = update.pop("risk_flags", None)
        if snapshot:
            snapshots.append(snapshot)
        if source and source not in sources:
            sources.append(source)
        if flags:
            risk_flags.extend(flag for flag in flags if flag not in risk_flags)
        for key, value in update.items():
            if value is not None:
                if key in {"txns", "txns_1h", "txns_5m"} and isinstance(value, dict):
                    value = txns(value)
                values[key] = value
    values["provider_snapshots"] = snapshots
    values["sources"] = sources
    values["risk_flags"] = risk_flags
    return TokenLaunch(**values)
