from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from tempfile import gettempdir

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.database.session import SessionFactory
from app.intelligence.wallet_export import WalletReportExporter
from app.intelligence.wallet_message import build_wallet_report_completed_message
from app.intelligence.wallet_ranking import WalletRankingEngine
from app.intelligence.wallet_report import WalletReportEngine
from app.intelligence.wallet_review import WalletReviewService
from app.telegram.client import TelegramClient

router = APIRouter(prefix="/admin", tags=["wallet-intelligence"])


class ReviewRequest(BaseModel):
    wallet_id: int
    reviewed_by: str | None = "admin"
    notes: str | None = None


async def _send_report_complete_message(export: dict[str, object]) -> None:
    settings = get_settings()
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return
    client = TelegramClient(settings.telegram_bot_token)
    try:
        await client.send_message(settings.telegram_chat_id, build_wallet_report_completed_message(export))
        await client.send_document(
            settings.telegram_chat_id,
            str(export["pdf_path"]),
            caption="Wallet Intelligence Report PDF. Candidate wallets only; manual approval is required before alerts.",
        )
    finally:
        await client.close()


@router.get("/reports")
async def reports(send_telegram: bool = True) -> dict[str, object]:
    async with SessionFactory() as session:
        generated = await WalletReportEngine(session).reports()
        export = WalletReportExporter().export(generated, Path(gettempdir()) / "nexora-reports")
    if send_telegram:
        await _send_report_complete_message(export)
    return export


@router.get("/rankings")
async def rankings() -> list[dict[str, object]]:
    async with SessionFactory() as session:
        generated = await WalletReportEngine(session).reports()
    return [asdict(report) for report in WalletRankingEngine().rank(generated)]


@router.get("/wallet/{wallet_id}")
async def wallet_report(wallet_id: int) -> dict[str, object]:
    async with SessionFactory() as session:
        try:
            report = await WalletReportEngine(session).report_for_wallet(wallet_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return asdict(report)


@router.post("/approve-wallet")
async def approve_wallet(payload: ReviewRequest) -> dict[str, object]:
    async with SessionFactory() as session:
        try:
            review = await WalletReviewService(session, get_settings()).approve(
                payload.wallet_id,
                reviewed_by=payload.reviewed_by,
                notes=payload.notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"approved": True, "wallet_id": review.wallet_id, "approved_for_signals": review.approved_for_signals}


@router.post("/reject-wallet")
async def reject_wallet(payload: ReviewRequest) -> dict[str, object]:
    async with SessionFactory() as session:
        try:
            review = await WalletReviewService(session, get_settings()).reject(
                payload.wallet_id,
                reviewed_by=payload.reviewed_by,
                notes=payload.notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"rejected": True, "wallet_id": review.wallet_id}


@router.post("/needs-observation")
async def needs_observation(payload: ReviewRequest) -> dict[str, object]:
    async with SessionFactory() as session:
        try:
            review = await WalletReviewService(session, get_settings()).needs_observation(
                payload.wallet_id,
                reviewed_by=payload.reviewed_by,
                notes=payload.notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"needs_observation": True, "wallet_id": review.wallet_id}
