from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select

from app.collectors.base import BaseCollector
from app.core.config import Settings
from app.core.logging import get_logger
from app.models import Wallet, WalletScore
from app.schemas.records import TokenRecord, TransactionRecord
from app.services.http import AsyncAPIClient, ExternalAPIError

logger = get_logger(__name__)


class BlockchainCollector(BaseCollector):
    def __init__(
        self,
        session,
        settings: Settings,
        client: AsyncAPIClient | None = None,
        moralis_client: AsyncAPIClient | None = None,
    ) -> None:
        self.settings = settings
        self.moralis_client = moralis_client
        super().__init__(
            session,
            client
            or AsyncAPIClient(
                "https://api.etherscan.io", timeout=settings.http_timeout_seconds,
                max_retries=settings.http_max_retries,
            ),
        )
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

    async def _fetch(self, action: str, **params: Any) -> list[dict[str, Any]]:
        if not self.settings.etherscan_api_key:
            logger.info("collector_skipped", collector="blockchain", reason="missing_api_key")
            return []
        payload = await self.client.request_json(
            "GET",
            "/v2/api",
            params={
                "chainid": self.settings.etherscan_chain_id,
                "module": "account",
                "action": action,
                "apikey": self.settings.etherscan_api_key,
                "sort": "asc",
                **params,
            },
        )
        if str(payload.get("status")) == "0":
            result = payload.get("result")
            if isinstance(result, str) and "No transactions" in result:
                return []
            raise ExternalAPIError(f"Etherscan rejected request: {result}")
        return payload.get("result", [])

    async def _fetch_moralis_token_transfers(self, wallet: str) -> list[dict[str, Any]]:
        if not self.settings.moralis_api_key or self.moralis_client is None:
            return []
        payload = await self.moralis_client.request_json(
            "GET",
            f"/api/v2.2/{wallet}/erc20/transfers",
            params={
                "chain": self.settings.moralis_chain,
                "order": "ASC",
                "limit": 100,
            },
            headers={"X-API-Key": self.settings.moralis_api_key},
        )
        return payload.get("result", []) if isinstance(payload, dict) else []

    @staticmethod
    def normalize_transaction(item: dict[str, Any], wallet: str, token_transfer: bool) -> TransactionRecord:
        decimals = int(item.get("tokenDecimal", "18") or 0) if token_transfer else 18
        amount = Decimal(item.get("value", "0")) / (Decimal(10) ** decimals)
        sender = str(item.get("from", "")).lower()
        token = None
        if token_transfer:
            token = TokenRecord(
                blockchain_address=item.get("contractAddress"),
                symbol=item.get("tokenSymbol") or "UNKNOWN",
                name=item.get("tokenName") or item.get("tokenSymbol") or "Unknown Token",
            )
        return TransactionRecord(
            external_id=f"{item['hash']}:{item.get('logIndex', 'native')}",
            wallet_address=wallet,
            token=token,
            transaction_type="out" if sender == wallet.lower() else "in",
            amount=amount,
            timestamp=datetime.fromtimestamp(int(item["timeStamp"]), tz=timezone.utc),
        )

    @staticmethod
    def normalize_moralis_token_transfer(item: dict[str, Any], wallet: str) -> TransactionRecord:
        decimals = int(item.get("token_decimals") or item.get("tokenDecimal") or 18)
        raw_value = item.get("value") or item.get("amount") or "0"
        amount = Decimal(str(raw_value)) / (Decimal(10) ** decimals)
        sender = str(item.get("from_address") or item.get("from") or "").lower()
        tx_hash = item.get("transaction_hash") or item.get("hash")
        log_index = item.get("log_index") or item.get("logIndex") or "token"
        timestamp_raw = item.get("block_timestamp") or item.get("blockTimestamp")
        if isinstance(timestamp_raw, str):
            timestamp = datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
        else:
            timestamp = datetime.fromtimestamp(int(item["block_timestamp"]), tz=timezone.utc)
        return TransactionRecord(
            external_id=f"{tx_hash}:{log_index}",
            wallet_address=wallet,
            token=TokenRecord(
                blockchain_address=item.get("token_address") or item.get("address"),
                symbol=item.get("token_symbol") or item.get("tokenSymbol") or "UNKNOWN",
                name=item.get("token_name") or item.get("tokenName") or item.get("token_symbol") or "Unknown Token",
            ),
            transaction_type="out" if sender == wallet.lower() else "in",
            amount=amount,
            timestamp=timestamp,
        )

    async def collect(self) -> int:
        stored = 0
        for wallet in await self._wallets_to_collect():
            if self.settings.moralis_api_key:
                for item in await self._fetch_moralis_token_transfers(wallet):
                    try:
                        record = self.normalize_moralis_token_transfer(item, wallet)
                        stored += int(await self.repository.add_transaction(record))
                    except (KeyError, ValueError, ValidationError) as exc:
                        logger.warning("invalid_moralis_blockchain_record", error=str(exc))
                continue
            for action, is_token in (("txlist", False), ("tokentx", True)):
                for item in await self._fetch(action, address=wallet, startblock=0, endblock=99999999):
                    try:
                        record = self.normalize_transaction(item, wallet, is_token)
                        stored += int(await self.repository.add_transaction(record))
                    except (KeyError, ValueError, ValidationError) as exc:
                        logger.warning("invalid_blockchain_record", error=str(exc))
        await self.session.commit()
        logger.info("collector_complete", collector="blockchain", stored=stored)
        return stored

    async def _wallets_to_collect(self) -> list[str]:
        configured = {wallet.lower() for wallet in self.settings.tracked_wallets}
        auto_tracked = (
            await self.session.scalars(
                select(Wallet.wallet_address)
                .join(WalletScore, WalletScore.wallet_id == Wallet.id)
                .where(WalletScore.id.in_(select(func.max(WalletScore.id)).group_by(WalletScore.wallet_id)))
                .where(WalletScore.final_smart_money_score >= self.settings.wallet_auto_track_threshold)
                .order_by(WalletScore.final_smart_money_score.desc(), WalletScore.id.desc())
                .limit(self.settings.wallet_auto_track_limit)
            )
        ).all()
        return sorted(configured | {wallet.lower() for wallet in auto_tracked})

    async def close(self) -> None:
        await super().close()
        if self.moralis_client is not None:
            await self.moralis_client.close()
