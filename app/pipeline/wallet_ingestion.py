from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.models import CandidateHistory, CandidatePortfolioSnapshot, CandidateTokenHistory, CandidateWallet
from app.services.http import AsyncAPIClient
from app.services.smart_money import aware

logger = get_logger(__name__)
ZERO = Decimal("0")
STABLECOINS = {
    "Es9vMFrzaCERmJfrF4H2FYD4KCo9VfBq9gmJEr4d8xX": "USDT",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
}


class WalletEvidenceProvider(Protocol):
    async def download_transactions(self, wallet: CandidateWallet) -> int:
        ...

    async def download_portfolio(self, wallet: CandidateWallet) -> bool:
        ...

    async def download_token_history(self, wallet: CandidateWallet) -> int:
        ...

    async def close(self) -> None:
        ...


class StoredWalletEvidenceProvider:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def download_transactions(self, wallet: CandidateWallet) -> int:
        return len(await self._history(wallet.id))

    async def download_portfolio(self, wallet: CandidateWallet) -> bool:
        history = await self._history(wallet.id)
        values = [Decimal(item.usd_value) for item in history if item.usd_value is not None]
        if not values:
            return False
        total_value = sum(values, ZERO)
        existing = await self._latest_snapshot(wallet.id)
        if existing is None:
            self.session.add(
                CandidatePortfolioSnapshot(
                    wallet_id=wallet.id,
                    total_value_usd=total_value,
                    largest_position_token=self._largest_token(history),
                    largest_position_usd=max(values, default=ZERO),
                    top_10_holdings=json.dumps([]),
                    stablecoin_allocation=ZERO,
                    portfolio_concentration=Decimal("100"),
                    zero_assets_confirmed=total_value == 0,
                )
            )
        return True

    async def download_token_history(self, wallet: CandidateWallet) -> int:
        return await build_token_history_from_candidate_history(self.session, wallet.id)

    async def close(self) -> None:
        return None

    async def _history(self, wallet_id: int) -> list[CandidateHistory]:
        return list(
            (
                await self.session.scalars(
                    select(CandidateHistory).where(CandidateHistory.wallet_id == wallet_id).order_by(CandidateHistory.timestamp)
                )
            ).all()
        )

    async def _latest_snapshot(self, wallet_id: int) -> CandidatePortfolioSnapshot | None:
        return await self.session.scalar(
            select(CandidatePortfolioSnapshot)
            .where(CandidatePortfolioSnapshot.wallet_id == wallet_id)
            .order_by(CandidatePortfolioSnapshot.created_at.desc(), CandidatePortfolioSnapshot.id.desc())
        )

    @staticmethod
    def _largest_token(history: list[CandidateHistory]) -> str | None:
        totals: dict[str, Decimal] = defaultdict(Decimal)
        for item in history:
            totals[item.token] += Decimal(item.usd_value or 0)
        return max(totals, key=totals.get, default=None)


class SolanaWalletEvidenceProvider(StoredWalletEvidenceProvider):
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        rpc_client: httpx.AsyncClient | None = None,
        dexscreener_client: AsyncAPIClient | None = None,
    ) -> None:
        super().__init__(session)
        self.settings = settings
        self._owns_rpc_client = rpc_client is None
        self.rpc_client = rpc_client or httpx.AsyncClient(
            base_url="https://api.mainnet-beta.solana.com",
            timeout=settings.http_timeout_seconds,
        )
        self.dexscreener_client = dexscreener_client or AsyncAPIClient(
            "https://api.dexscreener.com",
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )
        self.moralis_client = AsyncAPIClient(
            "https://solana-gateway.moralis.io",
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
            headers={"accept": "application/json", "X-API-Key": settings.moralis_api_key or ""},
        )
        self._price_cache: dict[str, Decimal | None] = {}

    async def download_transactions(self, wallet: CandidateWallet) -> int:
        try:
            signatures = await self._signatures(wallet.wallet_address)
        except httpx.HTTPStatusError as exc:
            logger.info(
                "solana_rpc_history_unavailable_using_moralis",
                wallet=wallet.wallet_address,
                status_code=exc.response.status_code,
            )
            return await self._download_moralis_transactions(wallet)
        stored = 0
        for signature in signatures:
            if await self._signature_exists(wallet.id, signature):
                continue
            transaction = await self._transaction(signature)
            stored += await self._store_transaction(wallet, signature, transaction)
        return stored + len(await self._history(wallet.id))

    async def download_portfolio(self, wallet: CandidateWallet) -> bool:
        try:
            holdings = await self._token_accounts(wallet.wallet_address)
        except httpx.HTTPStatusError as exc:
            logger.info(
                "solana_rpc_portfolio_unavailable_using_moralis",
                wallet=wallet.wallet_address,
                status_code=exc.response.status_code,
            )
            holdings = await self._moralis_portfolio(wallet.wallet_address)
        priced_holdings = []
        for holding in holdings:
            price = await self._token_price(holding["token"])
            usd_value = None if price is None else holding["amount"] * price
            priced_holdings.append({**holding, "usd_value": usd_value})
        confirmed_zero = len(holdings) == 0
        known_values = [item["usd_value"] for item in priced_holdings if item["usd_value"] is not None]
        total_value = sum(known_values, ZERO) if known_values else (ZERO if confirmed_zero else None)
        largest = max(priced_holdings, key=lambda item: item["usd_value"] or ZERO, default=None)
        top = sorted(priced_holdings, key=lambda item: item["usd_value"] or ZERO, reverse=True)[:10]
        stable_value = sum((item["usd_value"] or ZERO for item in priced_holdings if item["token"] in STABLECOINS), ZERO)
        concentration = ((largest["usd_value"] or ZERO) / total_value * Decimal("100")) if total_value and largest else None
        stable_allocation = (stable_value / total_value * Decimal("100")) if total_value else (ZERO if confirmed_zero else None)
        self.session.add(
            CandidatePortfolioSnapshot(
                wallet_id=wallet.id,
                total_value_usd=total_value,
                largest_position_token=largest["token"] if largest else None,
                largest_position_usd=largest["usd_value"] if largest else None,
                top_10_holdings=json.dumps(top, default=str),
                stablecoin_allocation=stable_allocation,
                portfolio_concentration=concentration,
                zero_assets_confirmed=confirmed_zero,
            )
        )
        return total_value is not None

    async def close(self) -> None:
        await self.moralis_client.close()
        await self.dexscreener_client.close()
        if self._owns_rpc_client:
            await self.rpc_client.aclose()

    async def _download_moralis_transactions(self, wallet: CandidateWallet) -> int:
        if not self.settings.moralis_api_key:
            return len(await self._history(wallet.id))
        try:
            payload = await self.moralis_client.request_json(
                "GET",
                f"/account/mainnet/{wallet.wallet_address}/transfers",
                params={"limit": self.settings.candidate_history_signature_limit},
                headers={"X-API-Key": self.settings.moralis_api_key},
            )
        except Exception as exc:
            logger.info("moralis_wallet_history_unavailable", wallet=wallet.wallet_address, error=type(exc).__name__)
            return len(await self._history(wallet.id))
        raw_items = payload.get("result", payload) if isinstance(payload, dict) else payload
        items = raw_items if isinstance(raw_items, list) else []
        stored = 0
        for item in items:
            normalized = self._normalize_moralis_transfer(item)
            if normalized is None or await self._signature_exists(wallet.id, normalized["signature"]):
                continue
            self.session.add(
                CandidateHistory(
                    wallet_id=wallet.id,
                    signature=normalized["signature"],
                    token=normalized["token"],
                    action=normalized["action"],
                    direction=normalized["direction"],
                    amount=normalized["amount"],
                    usd_value=normalized["usd_value"],
                    dex=normalized["dex"],
                    fees=normalized["fees"],
                    counterparty=normalized["counterparty"],
                    timestamp=normalized["timestamp"],
                )
            )
            stored += 1
        return stored + len(await self._history(wallet.id))

    async def _moralis_portfolio(self, wallet_address: str) -> list[dict[str, Any]]:
        if not self.settings.moralis_api_key:
            return []
        try:
            payload = await self.moralis_client.request_json(
                "GET",
                f"/account/mainnet/{wallet_address}/portfolio",
                headers={"X-API-Key": self.settings.moralis_api_key},
            )
        except Exception as exc:
            logger.info("moralis_wallet_portfolio_unavailable", wallet=wallet_address, error=type(exc).__name__)
            return []
        raw_tokens = []
        if isinstance(payload, dict):
            raw_tokens = payload.get("tokens") or payload.get("result") or payload.get("items") or []
        elif isinstance(payload, list):
            raw_tokens = payload
        holdings = []
        for item in raw_tokens if isinstance(raw_tokens, list) else []:
            if not isinstance(item, dict):
                continue
            token = item.get("mint") or item.get("tokenAddress") or item.get("token_address") or item.get("address")
            amount = decimal_or_zero(item.get("amount") or item.get("balance") or item.get("uiAmount"))
            if token and amount > 0:
                holdings.append({"token": str(token), "amount": amount})
        return holdings

    async def _signatures(self, address: str) -> list[str]:
        signatures: list[str] = []
        before: str | None = None
        limit = min(self.settings.candidate_history_signature_limit, 1000)
        while len(signatures) < self.settings.candidate_history_signature_limit:
            params: dict[str, Any] = {"limit": min(1000, self.settings.candidate_history_signature_limit - len(signatures))}
            if before:
                params["before"] = before
            payload = await self._rpc("getSignaturesForAddress", [address, params])
            result = payload.get("result", []) if isinstance(payload, dict) else []
            if not result:
                break
            batch = [str(item["signature"]) for item in result if isinstance(item, dict) and item.get("signature")]
            signatures.extend(batch)
            before = batch[-1] if batch else None
            if len(batch) < limit:
                break
        return signatures

    async def _transaction(self, signature: str) -> dict[str, Any] | None:
        payload = await self._rpc("getTransaction", [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        result = payload.get("result") if isinstance(payload, dict) else None
        return result if isinstance(result, dict) else None

    async def _store_transaction(self, wallet: CandidateWallet, signature: str, transaction: dict[str, Any] | None) -> int:
        if not transaction:
            return 0
        timestamp = datetime.fromtimestamp(int(transaction.get("blockTime") or datetime.now(timezone.utc).timestamp()), tz=timezone.utc)
        meta = transaction.get("meta") or {}
        fee = Decimal(str(meta.get("fee") or 0)) / Decimal("1000000000")
        rows = self._token_balance_changes(wallet.wallet_address, meta)
        if not rows:
            return 0
        for row in rows:
            self.session.add(
                CandidateHistory(
                    wallet_id=wallet.id,
                    signature=signature,
                    token=row["token"],
                    action=row["direction"],
                    direction=row["direction"],
                    amount=row["amount"],
                    usd_value=None,
                    dex=self._detect_dex(transaction),
                    fees=fee,
                    counterparty=self._counterparty(wallet.wallet_address, transaction),
                    timestamp=timestamp,
                )
            )
        return len(rows)

    @staticmethod
    def _token_balance_changes(wallet_address: str, meta: dict[str, Any]) -> list[dict[str, Any]]:
        before = SolanaWalletEvidenceProvider._balances_by_account(meta.get("preTokenBalances") or [], wallet_address)
        after = SolanaWalletEvidenceProvider._balances_by_account(meta.get("postTokenBalances") or [], wallet_address)
        rows = []
        for key in set(before) | set(after):
            token = key[1]
            delta = after.get(key, ZERO) - before.get(key, ZERO)
            if delta == 0:
                continue
            rows.append({"token": token, "direction": "buy" if delta > 0 else "sell", "amount": abs(delta)})
        return rows

    @staticmethod
    def _balances_by_account(items: list[dict[str, Any]], owner: str) -> dict[tuple[int, str], Decimal]:
        balances = {}
        for item in items:
            if item.get("owner") != owner:
                continue
            amount = ((item.get("uiTokenAmount") or {}).get("uiAmountString") or "0")
            balances[(int(item.get("accountIndex") or 0), str(item.get("mint")))] = decimal_or_zero(amount)
        return balances

    async def _token_accounts(self, address: str) -> list[dict[str, Any]]:
        payload = await self._rpc(
            "getTokenAccountsByOwner",
            [address, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}, {"encoding": "jsonParsed"}],
        )
        accounts = ((payload.get("result") or {}).get("value") or []) if isinstance(payload, dict) else []
        holdings = []
        for account in accounts:
            parsed = ((((account.get("account") or {}).get("data") or {}).get("parsed") or {}).get("info") or {})
            token_amount = parsed.get("tokenAmount") or {}
            amount = decimal_or_zero(token_amount.get("uiAmountString") or token_amount.get("uiAmount"))
            if amount <= 0:
                continue
            holdings.append({"token": str(parsed.get("mint")), "amount": amount})
        return holdings

    async def _token_price(self, token: str) -> Decimal | None:
        if token in self._price_cache:
            return self._price_cache[token]
        try:
            payload = await self.dexscreener_client.request_json("GET", f"/token-pairs/v1/solana/{token}")
        except Exception as exc:
            logger.info("dex_price_unavailable", token=token, error=type(exc).__name__)
            self._price_cache[token] = None
            return None
        pairs = payload if isinstance(payload, list) else []
        prices = [decimal_or_none(pair.get("priceUsd")) for pair in pairs if isinstance(pair, dict)]
        price = next((item for item in prices if item is not None and item > 0), None)
        self._price_cache[token] = price
        return price

    async def _signature_exists(self, wallet_id: int, signature: str) -> bool:
        existing = await self.session.scalar(
            select(CandidateHistory.id).where(CandidateHistory.wallet_id == wallet_id, CandidateHistory.signature == signature)
        )
        return existing is not None

    async def _rpc(self, method: str, params: list[Any]) -> dict[str, Any]:
        response = await self.rpc_client.post("/", json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise RuntimeError(str(payload["error"]))
        return payload

    @staticmethod
    def _normalize_moralis_transfer(item: dict[str, Any]) -> dict[str, Any] | None:
        token = item.get("mint") or item.get("token_address") or item.get("tokenAddress") or item.get("tokenMint") or item.get("address")
        signature = item.get("signature") or item.get("transactionHash") or item.get("transaction_hash")
        if not token or not signature:
            return None
        action = str(item.get("type") or item.get("transactionType") or "transfer").lower()
        direction = "sell" if action in {"sell", "out"} else "buy"
        timestamp_raw = item.get("blockTimestamp") or item.get("block_timestamp") or item.get("timestamp")
        if isinstance(timestamp_raw, str):
            timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
        else:
            timestamp = datetime.fromtimestamp(int(timestamp_raw or datetime.now(timezone.utc).timestamp()), tz=timezone.utc)
        return {
            "signature": str(signature),
            "token": str(token),
            "action": action,
            "direction": direction,
            "amount": decimal_or_zero(item.get("amount") or item.get("value") or item.get("tokenAmount")),
            "usd_value": decimal_or_none(item.get("usdValue") or item.get("usd_value") or item.get("valueUsd")),
            "dex": item.get("exchange") or item.get("dex"),
            "fees": decimal_or_none(item.get("fee") or item.get("fees")),
            "counterparty": item.get("from_address") or item.get("to_address") or item.get("counterparty"),
            "timestamp": timestamp,
        }

    @staticmethod
    def _detect_dex(transaction: dict[str, Any]) -> str | None:
        text = json.dumps(transaction)[:20000].lower()
        for name in ("raydium", "orca", "jupiter", "meteora", "pump"):
            if name in text:
                return name
        return None

    @staticmethod
    def _counterparty(wallet_address: str, transaction: dict[str, Any]) -> str | None:
        message = ((transaction.get("transaction") or {}).get("message") or {})
        keys = message.get("accountKeys") or []
        for account in keys:
            pubkey = account.get("pubkey") if isinstance(account, dict) else account
            if pubkey and pubkey != wallet_address:
                return str(pubkey)
        return None


async def build_token_history_from_candidate_history(session: AsyncSession, wallet_id: int) -> int:
    history = list(
        (
            await session.scalars(
                select(CandidateHistory).where(CandidateHistory.wallet_id == wallet_id).order_by(CandidateHistory.timestamp)
            )
        ).all()
    )
    grouped: dict[str, list[CandidateHistory]] = defaultdict(list)
    for item in history:
        grouped[item.token].append(item)
    stored = 0
    for token, rows in grouped.items():
        buys = [row for row in rows if row.action.lower() in {"buy", "swap", "accumulate", "liquidity_add"}]
        sells = [row for row in rows if row.action.lower() in {"sell", "out", "liquidity_remove"}]
        if len(rows) < 2:
            continue
        average_entry = average_usd(buys)
        average_exit = average_usd(sells)
        roi = ((average_exit - average_entry) / average_entry * Decimal("100")) if average_entry and average_exit else None
        holding_days = Decimal(str((aware(rows[-1].timestamp) - aware(rows[0].timestamp)).total_seconds() / 86400))
        existing = await session.scalar(
            select(CandidateTokenHistory).where(CandidateTokenHistory.wallet_id == wallet_id, CandidateTokenHistory.token == token)
        )
        token_history = existing or CandidateTokenHistory(wallet_id=wallet_id, token=token)
        token_history.purchase_count = len(buys)
        token_history.sale_count = len(sells)
        token_history.average_entry_usd = average_entry
        token_history.average_exit_usd = average_exit
        token_history.holding_duration_days = holding_days
        token_history.roi = roi
        token_history.current_status = "closed" if sells else "open"
        session.add(token_history)
        stored += 1
    return stored


def average_usd(rows: list[CandidateHistory]) -> Decimal | None:
    values = [Decimal(row.usd_value) for row in rows if row.usd_value is not None]
    return sum(values, ZERO) / Decimal(len(values)) if values else None


def decimal_or_zero(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return ZERO


def decimal_or_none(value: Any) -> Decimal | None:
    try:
        return None if value is None else Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
