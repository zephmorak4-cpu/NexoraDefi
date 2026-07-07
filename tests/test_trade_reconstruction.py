from datetime import datetime, timedelta, timezone
from decimal import Decimal
from contextlib import asynccontextmanager

import httpx

from app.main import app
from app.models import CandidateHistory, CandidateWallet, WalletPosition
from app.trade_reconstruction.trade_reconstruction import TradeReconstructionEngine


async def _wallet_with_position_history(db_session) -> CandidateWallet:
    wallet = CandidateWallet(
        wallet_address="position-wallet",
        chain="solana",
        discovery_reason="test",
        status="observing",
        pipeline_stage="RANKED",
        pipeline_status="READY",
    )
    db_session.add(wallet)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            CandidateHistory(wallet_id=wallet.id, signature="buy-1", token="TokenA", action="buy", amount=Decimal("10"), usd_value=Decimal("100"), timestamp=now - timedelta(days=5)),
            CandidateHistory(wallet_id=wallet.id, signature="buy-2", token="TokenA", action="buy", amount=Decimal("10"), usd_value=Decimal("200"), timestamp=now - timedelta(days=4)),
            CandidateHistory(wallet_id=wallet.id, signature="sell-1", token="TokenA", action="sell", amount=Decimal("5"), usd_value=Decimal("125"), timestamp=now - timedelta(days=2)),
            CandidateHistory(wallet_id=wallet.id, signature="sell-2", token="TokenA", action="sell", amount=Decimal("15"), usd_value=Decimal("450"), timestamp=now - timedelta(days=1)),
        ]
    )
    await db_session.commit()
    return wallet


async def test_trade_reconstruction_builds_one_position_from_many_events(db_session):
    wallet = await _wallet_with_position_history(db_session)

    rebuilt = await TradeReconstructionEngine(db_session).rebuild_wallet(wallet.id)
    await db_session.commit()

    position = (await TradeReconstructionEngine(db_session).positions("position-wallet"))[0]
    assert rebuilt == 1
    assert position.token_address == "TokenA"
    assert position.quantity_bought == Decimal("20.000000000000000000")
    assert position.quantity_sold == Decimal("20.000000000000000000")
    assert position.position_status == "CLOSED"
    assert position.average_entry_price == Decimal("15.000000000000000000")
    assert position.average_exit_price == Decimal("28.750000000000000000")
    assert position.realized_roi > 0
    assert position.position_classification in {"Swing Trade", "Quick Flip", "Scalp"}


async def test_trade_reconstruction_admin_api(db_session, monkeypatch):
    from app.trade_reconstruction import trade_reconstruction_api

    wallet = await _wallet_with_position_history(db_session)

    @asynccontextmanager
    async def fake_session_factory():
        yield db_session

    monkeypatch.setattr(trade_reconstruction_api, "SessionFactory", fake_session_factory)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        rebuilt = await client.post("/admin/rebuild-positions")
        positions = await client.get("/admin/positions")
        wallet_positions = await client.get(f"/admin/positions/{wallet.wallet_address}")
        summary = await client.get("/admin/position-summary")
        position_id = positions.json()[0]["id"]
        detail = await client.get(f"/admin/position/{position_id}")

    assert rebuilt.status_code == 200
    assert rebuilt.json()["positions"] == 1
    assert positions.status_code == 200
    assert wallet_positions.status_code == 200
    assert summary.json()["total_positions"] == 1
    assert detail.json()["token_address"] == "TokenA"


async def test_wallet_positions_table_accepts_reconstructed_candidate_positions(db_session):
    wallet = CandidateWallet(wallet_address="table-wallet", chain="solana", discovery_reason="test", status="observing")
    db_session.add(wallet)
    await db_session.flush()
    db_session.add(
        WalletPosition(
            candidate_wallet_id=wallet.id,
            token_address="TokenA",
            entry_time=datetime.now(timezone.utc),
            latest_activity_date=datetime.now(timezone.utc),
            average_entry_price=Decimal("1"),
        )
    )
    await db_session.commit()


async def test_reconstruction_rejects_closed_position_without_cost_basis(db_session):
    wallet = CandidateWallet(wallet_address="no-cost-wallet", chain="solana", discovery_reason="test", status="observing")
    db_session.add(wallet)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            CandidateHistory(wallet_id=wallet.id, signature="buy", token="TokenX", action="buy", amount=Decimal("1"), usd_value=None, timestamp=now - timedelta(days=1)),
            CandidateHistory(wallet_id=wallet.id, signature="sell", token="TokenX", action="sell", amount=Decimal("1"), usd_value=None, timestamp=now),
        ]
    )
    await db_session.commit()

    rebuilt = await TradeReconstructionEngine(db_session).rebuild_wallet(wallet.id)

    assert rebuilt == 0
