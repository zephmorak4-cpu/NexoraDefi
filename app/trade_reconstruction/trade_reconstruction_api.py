from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.database.session import SessionFactory
from app.models import WalletPosition
from app.trade_reconstruction.position_summary import PositionSummary
from app.trade_reconstruction.trade_reconstruction import TradeReconstructionEngine

router = APIRouter(prefix="/admin", tags=["trade-reconstruction"])


class WalletPositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_wallet_id: int | None
    token_address: str | None
    token_symbol: str | None
    entry_time: datetime | None
    final_exit_time: datetime | None
    first_buy_signature: str | None
    last_sell_signature: str | None
    average_entry_price: Decimal
    average_exit_price: Decimal
    quantity_bought: Decimal
    quantity_sold: Decimal
    remaining_quantity: Decimal
    position_status: str
    holding_period: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    realized_roi: Decimal
    maximum_position_size: Decimal
    number_of_buys: int
    number_of_sells: int
    accumulation_events: int
    distribution_events: int
    largest_buy: Decimal
    largest_sell: Decimal
    position_classification: str
    position_quality_score: Decimal
    ai_analysis: str | None


@router.get("/positions", response_model=list[WalletPositionResponse])
async def positions() -> list[WalletPosition]:
    async with SessionFactory() as session:
        return await TradeReconstructionEngine(session).positions()


@router.get("/positions/{wallet}", response_model=list[WalletPositionResponse])
async def positions_for_wallet(wallet: str) -> list[WalletPosition]:
    async with SessionFactory() as session:
        return await TradeReconstructionEngine(session).positions(wallet)


@router.get("/position/{position_id}", response_model=WalletPositionResponse)
async def position(position_id: int) -> WalletPosition:
    async with SessionFactory() as session:
        item = await session.get(WalletPosition, position_id)
        if item is None or item.candidate_wallet_id is None:
            raise HTTPException(status_code=404, detail="position not found")
        return item


@router.get("/position-summary")
async def position_summary() -> dict[str, object]:
    async with SessionFactory() as session:
        return PositionSummary().build(await TradeReconstructionEngine(session).positions())


@router.post("/rebuild-positions")
async def rebuild_positions() -> dict[str, int]:
    async with SessionFactory() as session:
        rebuilt = await TradeReconstructionEngine(session).rebuild_all()
        return {"positions": rebuilt}
