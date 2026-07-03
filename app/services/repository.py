from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import NewsArticle, PriceHistory, SocialSignal, Token, Transaction, Wallet
from app.schemas.records import NewsRecord, PriceRecord, SocialRecord, TokenRecord, TransactionRecord


class DataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_token(self, record: TokenRecord) -> Token:
        query = select(Token).where(Token.chain == record.chain)
        if record.blockchain_address:
            query = query.where(Token.blockchain_address == record.blockchain_address.lower())
        else:
            query = query.where(Token.symbol == record.symbol.upper())
        token = await self.session.scalar(query)
        if token:
            token.name = record.name
            token.symbol = record.symbol.upper()
            token.category = record.category
            return token
        token = Token(
            blockchain_address=(record.blockchain_address or "").lower() or None,
            symbol=record.symbol.upper(),
            name=record.name,
            chain=record.chain,
            category=record.category,
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_or_create_wallet(self, address: str, chain: str = "ethereum") -> Wallet:
        address = address.lower()
        wallet = await self.session.scalar(
            select(Wallet).where(Wallet.chain == chain, Wallet.wallet_address == address)
        )
        if wallet:
            return wallet
        wallet = Wallet(wallet_address=address, chain=chain)
        self.session.add(wallet)
        await self.session.flush()
        return wallet

    async def add_transaction(self, record: TransactionRecord) -> bool:
        wallet = await self.get_or_create_wallet(record.wallet_address)
        exists = await self.session.scalar(
            select(Transaction.id).where(
                Transaction.wallet_id == wallet.id, Transaction.external_id == record.external_id
            )
        )
        if exists:
            return False
        token = await self.get_or_create_token(record.token) if record.token else None
        self.session.add(
            Transaction(
                wallet_id=wallet.id,
                token_id=token.id if token else None,
                external_id=record.external_id,
                transaction_type=record.transaction_type,
                amount=record.amount,
                price=record.price,
                timestamp=record.timestamp,
            )
        )
        return True

    async def add_price(self, record: PriceRecord) -> bool:
        token = await self.session.scalar(select(Token).where(Token.category == record.coin_id))
        if token is None:
            candidates = list(
                (
                    await self.session.scalars(
                        select(Token).where(Token.symbol == record.symbol.upper()).limit(2)
                    )
                ).all()
            )
            if len(candidates) == 1:
                token = candidates[0]
                token.category = record.coin_id
                token.name = record.name
            else:
                token = await self.get_or_create_token(
                    TokenRecord(
                        symbol=record.symbol,
                        name=record.name,
                        chain="market",
                        category=record.coin_id,
                    )
                )
        exists = await self.session.scalar(
            select(PriceHistory.id).where(
                PriceHistory.token_id == token.id, PriceHistory.timestamp == record.timestamp
            )
        )
        if exists:
            return False
        self.session.add(
            PriceHistory(
                token_id=token.id,
                price=record.price,
                market_cap=record.market_cap,
                volume=record.volume,
                liquidity_value=record.liquidity_value,
                timestamp=record.timestamp,
            )
        )
        return True

    async def add_social(self, record: SocialRecord) -> bool:
        token = await self.get_or_create_token(
            TokenRecord(symbol=record.symbol, name=record.name, chain="market", category=record.coin_id)
        )
        exists = await self.session.scalar(
            select(SocialSignal.id).where(
                SocialSignal.token_id == token.id,
                SocialSignal.source == record.source,
                SocialSignal.timestamp == record.timestamp,
            )
        )
        if exists:
            return False
        self.session.add(
            SocialSignal(
                token_id=token.id,
                source=record.source,
                mentions=record.mentions,
                sentiment_score=record.sentiment_score,
                timestamp=record.timestamp,
            )
        )
        return True

    async def add_news(self, record: NewsRecord) -> bool:
        if await self.session.scalar(
            select(NewsArticle.id).where(NewsArticle.external_id == record.external_id)
        ):
            return False
        self.session.add(
            NewsArticle(
                external_id=record.external_id,
                title=record.title,
                url=str(record.url),
                source=record.source,
                sentiment=record.sentiment,
                published_at=record.published_at,
            )
        )
        return True
