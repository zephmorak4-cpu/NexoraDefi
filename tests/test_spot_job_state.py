from datetime import datetime, timedelta, timezone

from app.models import SpotJobLock
from app.spot.job_state import JobStateService, guarded_job


async def test_job_lock_prevents_duplicate_worker(db_session):
    service = JobStateService(db_session)
    first = await service.acquire_lock("SCAN_SETUPS", ttl_seconds=300)
    second = await service.acquire_lock("SCAN_SETUPS", ttl_seconds=300)

    assert first is not None
    assert second is None


async def test_expired_job_lock_can_be_recovered(db_session):
    service = JobStateService(db_session)
    first = await service.acquire_lock("SCAN_SETUPS", ttl_seconds=1)
    row = await service.session.get(SpotJobLock, "SCAN_SETUPS")
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    second = await service.acquire_lock("SCAN_SETUPS", ttl_seconds=300)

    assert first is not None
    assert second is not None
    assert second != first


async def test_guarded_job_records_successful_execution(db_session):
    async def work():
        return {"tokens_evaluated": 3}

    result = await guarded_job(db_session, "SCAN_SETUPS", work)
    latest = await JobStateService(db_session).latest_success("SCAN_SETUPS")

    assert result["status"] == "SUCCEEDED"
    assert latest is not None
    assert latest.records_processed == 3
