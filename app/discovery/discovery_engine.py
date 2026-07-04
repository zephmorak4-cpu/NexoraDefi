from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.discovery.candidate_wallet import CandidateWalletRepository, DiscoveryEvent
from app.discovery.wallet_history import WalletHistoryService
from app.discovery.wallet_classifier import WalletClassifier
from app.services.http import AsyncAPIClient

logger = get_logger(__name__)


class DiscoverySource(Protocol):
    async def events(self) -> list[DiscoveryEvent]:
        ...

    async def close(self) -> None:
        ...


class SolanaDiscoverySource:
    def __init__(
        self,
        settings: Settings,
        dexscreener_client: AsyncAPIClient | None = None,
        moralis_client: AsyncAPIClient | None = None,
        solana_rpc_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.dexscreener_client = dexscreener_client or AsyncAPIClient(
            "https://api.dexscreener.com",
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )
        self.moralis_client = moralis_client or AsyncAPIClient(
            "https://solana-gateway.moralis.io",
            timeout=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
            headers={"accept": "application/json", "X-API-Key": settings.moralis_api_key or ""},
        )
        self._owns_rpc_client = solana_rpc_client is None
        self.solana_rpc_client = solana_rpc_client or httpx.AsyncClient(
            base_url="https://api.mainnet-beta.solana.com",
            timeout=settings.http_timeout_seconds,
        )

    async def events(self) -> list[DiscoveryEvent]:
        if not self.settings.moralis_api_key:
            return []
        profiles = await self.dexscreener_client.request_json("GET", "/token-profiles/latest/v1")
        items = profiles if isinstance(profiles, list) else [profiles] if isinstance(profiles, dict) else []
        events: list[DiscoveryEvent] = []
        solana_profiles = [
            profile
            for profile in items
            if isinstance(profile, dict) and profile.get("chainId") == "solana" and profile.get("tokenAddress")
        ]
        for profile in solana_profiles[: self.settings.discovery_token_scan_limit]:
            token_address = str(profile["tokenAddress"])
            events.extend(await self._rpc_token_events(token_address, "interaction_with_trending_token"))
        return events

    async def _token_events(self, token_address: str, reason: str) -> list[DiscoveryEvent]:
        try:
            payload = await self.moralis_client.request_json(
                "GET",
                f"/token/mainnet/{token_address}/transfers",
                params={"limit": self.settings.discovery_transfer_limit},
                headers={"X-API-Key": self.settings.moralis_api_key or ""},
            )
        except Exception as exc:
            logger.info("moralis_token_transfer_discovery_unavailable", token=token_address, error=type(exc).__name__)
            return []
        raw_items = payload.get("result", payload) if isinstance(payload, dict) else payload
        if not isinstance(raw_items, list):
            return []
        events = []
        for item in raw_items:
            event = self._normalize_event(item, token_address, reason)
            if event is not None and self._passes_initial_filters(event):
                events.append(event)
        return events

    async def _rpc_token_events(self, token_address: str, reason: str) -> list[DiscoveryEvent]:
        scan_addresses = [token_address]
        scan_addresses.extend(await self._dex_pair_addresses(token_address))
        events: list[DiscoveryEvent] = []
        seen_wallets: set[str] = set()
        for address in scan_addresses[:3]:
            signatures = await self._rpc_signatures(address)
            for signature in signatures[: self.settings.discovery_transfer_limit]:
                for wallet in await self._rpc_transaction_signers(signature):
                    if wallet in seen_wallets or wallet in {token_address, address}:
                        continue
                    seen_wallets.add(wallet)
                    events.append(
                        DiscoveryEvent(
                            wallet_address=wallet,
                            token=token_address,
                            action="swap",
                            amount=Decimal("0"),
                            usd_value=None,
                            timestamp=datetime.now(timezone.utc),
                            reason=reason,
                        )
                    )
        return events

    async def _dex_pair_addresses(self, token_address: str) -> list[str]:
        try:
            payload = await self.dexscreener_client.request_json("GET", f"/token-pairs/v1/solana/{token_address}")
        except Exception as exc:
            logger.info("dex_pair_lookup_unavailable", token=token_address, error=type(exc).__name__)
            return []
        pairs = payload if isinstance(payload, list) else []
        return [
            str(pair["pairAddress"])
            for pair in pairs
            if isinstance(pair, dict) and pair.get("chainId") == "solana" and pair.get("pairAddress")
        ]

    async def _rpc_signatures(self, address: str) -> list[str]:
        try:
            response = await self.solana_rpc_client.post(
                "/",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getSignaturesForAddress",
                    "params": [address, {"limit": self.settings.discovery_transfer_limit}],
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.info("solana_rpc_signatures_unavailable", address=address, error=type(exc).__name__)
            return []
        result = payload.get("result", []) if isinstance(payload, dict) else []
        return [str(item["signature"]) for item in result if isinstance(item, dict) and item.get("signature")]

    async def _rpc_transaction_signers(self, signature: str) -> list[str]:
        try:
            response = await self.solana_rpc_client.post(
                "/",
                json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [signature, {"encoding": "json", "maxSupportedTransactionVersion": 0}],
            },
        )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.info("solana_rpc_transaction_unavailable", signature=signature, error=type(exc).__name__)
            return []
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            return []
        message = ((result.get("transaction") or {}).get("message") or {})
        account_keys = message.get("accountKeys") or []
        required_signatures = ((message.get("header") or {}).get("numRequiredSignatures") or 1)
        signers = []
        for account in account_keys[:required_signatures]:
            if isinstance(account, dict) and account.get("pubkey"):
                signers.append(str(account["pubkey"]))
            elif isinstance(account, str):
                signers.append(account)
        return signers

    def _passes_initial_filters(self, event: DiscoveryEvent) -> bool:
        return bool(
            event.wallet_address
            and event.wallet_address not in self.settings.discovery_blacklisted_wallets
            and (event.usd_value is None or event.usd_value >= Decimal(str(self.settings.discovery_min_usd_value)))
        )

    @classmethod
    def _normalize_event(cls, item: dict[str, Any], token_address: str, reason: str) -> DiscoveryEvent | None:
        wallet = item.get("owner") or item.get("from_address") or item.get("to_address") or item.get("walletAddress")
        if not wallet:
            return None
        timestamp_raw = item.get("blockTimestamp") or item.get("block_timestamp") or item.get("timestamp")
        if isinstance(timestamp_raw, str):
            timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
        else:
            timestamp = datetime.fromtimestamp(int(timestamp_raw or datetime.now(timezone.utc).timestamp()), tz=timezone.utc)
        usd_value = cls._decimal_or_none(item.get("usdValue") or item.get("usd_value") or item.get("valueUsd"))
        return DiscoveryEvent(
            wallet_address=str(wallet),
            token=str(item.get("tokenAddress") or item.get("mint") or token_address),
            action=str(item.get("type") or item.get("transactionType") or "swap").lower(),
            amount=cls._decimal_or_zero(item.get("amount") or item.get("value")),
            usd_value=usd_value,
            timestamp=timestamp,
            reason=reason,
        )

    @staticmethod
    def _decimal_or_zero(value: Any) -> Decimal:
        return Decimal(str(value or "0"))

    @staticmethod
    def _decimal_or_none(value: Any) -> Decimal | None:
        return None if value is None or value == "" else Decimal(str(value))

    async def close(self) -> None:
        await self.dexscreener_client.close()
        await self.moralis_client.close()
        if self._owns_rpc_client:
            await self.solana_rpc_client.aclose()


class DiscoveryEngine:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        source: DiscoverySource | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.source = source or SolanaDiscoverySource(settings)
        self.repository = CandidateWalletRepository(session)
        self.classifier = WalletClassifier()

    async def discover(self) -> int:
        events = await self.source.events()
        stored = 0
        for event in events:
            stored += int(await self.repository.upsert_event(event))
        history = WalletHistoryService(self.session)
        for wallet in await self.repository.candidates(statuses=("observing",)):
            wallet.wallet_type = self.classifier.classify(await history.for_candidate(wallet.id))
        await self.session.commit()
        logger.info("candidate_wallet_discovery_complete", events=len(events), new_candidates=stored)
        return stored

    async def close(self) -> None:
        await self.source.close()
