from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.blockchain import BlockchainCollector
from app.core.config import Settings
from app.core.logging import get_logger
from app.models import Token, Transaction, Wallet
from app.services.http import AsyncAPIClient
from app.services.repository import DataRepository
from app.services.smart_money import SmartMoneyScorer, WalletAnalyzer

logger = get_logger(__name__)


class WalletDiscoveryService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        moralis_client: AsyncAPIClient | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.repository = DataRepository(session)
        self.moralis_client = moralis_client
        if self.settings.moralis_api_key and self.moralis_client is None:
            self.moralis_client = AsyncAPIClient(
                "https://deep-index.moralis.io",
                timeout=settings.http_timeout_seconds,
                max_retries=settings.http_max_retries,
                headers={
                    "accept": "application/json",
                    "X-API-Key": self.settings.moralis_api_key,
                },
            )

    async def discover(self) -> int:
        if not self.settings.moralis_api_key or self.moralis_client is None:
            logger.info("wallet_discovery_skipped", reason="missing_moralis_api_key")
            return 0
        token_addresses = await self._known_token_addresses()
        stored = 0
        for token_address in token_addresses:
            transfers = await self._fetch_token_transfers(token_address)
            for item in transfers:
                stored += await self._store_transfer_wallet_sides(item)
        analyzed = await self.analyze_discovered_wallets()
        await self.session.commit()
        logger.info("wallet_discovery_complete", transactions=stored, wallets_analyzed=analyzed)
        return stored + analyzed

    async def _known_token_addresses(self) -> list[str]:
        rows = (
            await self.session.scalars(
                select(Token.blockchain_address)
                .where(Token.blockchain_address.is_not(None), Token.chain == "ethereum")
                .order_by(Token.updated_at.desc())
                .limit(self.settings.wallet_discovery_batch_size)
            )
        ).all()
        return [address for address in rows if address]

    async def _fetch_token_transfers(self, token_address: str) -> list[dict[str, Any]]:
        payload = await self.moralis_client.request_json(
            "GET",
            f"/api/v2.2/erc20/{token_address}/transfers",
            params={
                "chain": self.settings.moralis_chain,
                "order": "DESC",
                "limit": self.settings.wallet_discovery_transfer_limit,
            },
            headers={"X-API-Key": self.settings.moralis_api_key},
        )
        return payload.get("result", []) if isinstance(payload, dict) else []

    async def _store_transfer_wallet_sides(self, item: dict[str, Any]) -> int:
        stored = 0
        for wallet_key in ("from_address", "to_address"):
            wallet = item.get(wallet_key)
            if not wallet or str(wallet).lower() == "0x0000000000000000000000000000000000000000":
                continue
            try:
                record = BlockchainCollector.normalize_moralis_token_transfer(item, str(wallet))
                stored += int(await self.repository.add_transaction(record))
            except (KeyError, ValueError, ValidationError) as exc:
                logger.warning("invalid_wallet_discovery_record", error=str(exc))
        return stored

    async def analyze_discovered_wallets(self) -> int:
        wallet_rows = (
            await self.session.execute(
                select(Wallet.id, func.count(Transaction.id))
                .join(Transaction, Transaction.wallet_id == Wallet.id)
                .group_by(Wallet.id)
                .having(func.count(Transaction.id) >= self.settings.wallet_discovery_min_transactions)
                .order_by(func.count(Transaction.id).desc())
                .limit(self.settings.wallet_discovery_batch_size)
            )
        ).all()
        analyzer = WalletAnalyzer(self.session, self.settings)
        scorer = SmartMoneyScorer(self.session, self.settings)
        processed = 0
        now = datetime.now(timezone.utc)
        for wallet_id, _ in wallet_rows:
            await analyzer.analyze_wallet(wallet_id)
            processed += int(await scorer.score_wallet(wallet_id, now) is not None)
        return processed

    async def close(self) -> None:
        if self.moralis_client is not None:
            await self.moralis_client.close()
