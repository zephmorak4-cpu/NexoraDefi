from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select

from app.database.session import SessionFactory
from app.models import Alert, TokenQuality, TrackedWallet, WalletActivity
from app.smart_money.tracked_wallets import TrackedWalletManager

router = APIRouter(prefix="/admin", tags=["solana-smart-money-admin"])


class WalletAddRequest(BaseModel):
    wallet_address: str
    wallet_name: str | None = None
    wallet_label: str | None = None
    wallet_category: str | None = None
    chain: str = "solana"
    source: str = "manual"
    status: str = "active"
    notes: str | None = None


class WalletRemoveRequest(BaseModel):
    wallet_address: str
    chain: str = "solana"


class TrackedWalletResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_address: str
    wallet_name: str | None
    wallet_label: str | None
    wallet_category: str | None
    chain: str
    source: str
    status: str
    notes: str | None
    reputation_score: Decimal
    created_at: datetime
    updated_at: datetime


class WalletActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wallet_id: int
    token_address: str
    token_symbol: str
    transaction_signature: str
    transaction_type: str
    amount: Decimal
    usd_value: Decimal | None
    timestamp: datetime


class TokenQualityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token_address: str
    token_symbol: str
    quality_score: Decimal
    liquidity_score: Decimal
    volume_score: Decimal
    holder_score: Decimal
    age_score: Decimal
    market_cap_score: Decimal
    risk_score: Decimal
    calculated_at: datetime


@router.post("/wallets/add", response_model=TrackedWalletResponse)
async def add_wallet(payload: WalletAddRequest) -> TrackedWallet:
    async with SessionFactory() as session:
        return await TrackedWalletManager(session).add_wallet(**payload.model_dump())


@router.post("/wallets/remove")
async def remove_wallet(payload: WalletRemoveRequest) -> dict[str, bool]:
    async with SessionFactory() as session:
        removed = await TrackedWalletManager(session).remove_wallet(payload.wallet_address, payload.chain)
        if not removed:
            raise HTTPException(status_code=404, detail="tracked wallet not found")
        return {"removed": True}


@router.get("/wallets", response_model=list[TrackedWalletResponse])
async def wallets() -> list[TrackedWallet]:
    async with SessionFactory() as session:
        return list((await session.scalars(select(TrackedWallet).order_by(TrackedWallet.id))).all())


@router.get("/wallet-reputation", response_model=list[TrackedWalletResponse])
async def wallet_reputation() -> list[TrackedWallet]:
    async with SessionFactory() as session:
        return list(
            (
                await session.scalars(
                    select(TrackedWallet).order_by(desc(TrackedWallet.reputation_score), TrackedWallet.id)
                )
            ).all()
        )


@router.get("/token-quality", response_model=list[TokenQualityResponse])
async def token_quality() -> list[TokenQuality]:
    async with SessionFactory() as session:
        return list((await session.scalars(select(TokenQuality).order_by(desc(TokenQuality.quality_score)))).all())


@router.get("/conviction")
async def conviction() -> list[dict[str, object]]:
    async with SessionFactory() as session:
        rows = (
            await session.execute(
                select(WalletActivity, TrackedWallet)
                .join(TrackedWallet, TrackedWallet.id == WalletActivity.wallet_id)
                .order_by(desc(WalletActivity.timestamp))
                .limit(100)
            )
        ).all()
        return [
            {
                "wallet_address": wallet.wallet_address,
                "token_address": activity.token_address,
                "token_symbol": activity.token_symbol,
                "usd_value": activity.usd_value,
                "reputation_score": wallet.reputation_score,
                "timestamp": activity.timestamp,
            }
            for activity, wallet in rows
        ]


@router.get("/wallet-activity", response_model=list[WalletActivityResponse])
async def wallet_activity() -> list[WalletActivity]:
    async with SessionFactory() as session:
        return list((await session.scalars(select(WalletActivity).order_by(desc(WalletActivity.timestamp)).limit(100))).all())


@router.get("/signals")
async def admin_signals() -> list[dict[str, object]]:
    async with SessionFactory() as session:
        alerts = list(
            (
                await session.scalars(
                    select(Alert)
                    .where(Alert.alert_type.like("solana:%"))
                    .order_by(desc(Alert.created_at), desc(Alert.id))
                    .limit(100)
                )
            ).all()
        )
        return [
            {
                "id": alert.id,
                "message": alert.message,
                "confidence_score": alert.confidence_score,
                "created_at": alert.created_at,
            }
            for alert in alerts
        ]
