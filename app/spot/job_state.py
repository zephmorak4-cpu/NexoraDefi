from __future__ import annotations

import os
import socket
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SpotJobExecution, SpotJobLock


def build_version() -> str:
    return os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or "local"


def worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def utc_window(minutes: int = 5) -> datetime:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    minute = now.minute - (now.minute % minutes)
    return now.replace(minute=minute)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class JobStateService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def acquire_lock(self, job_name: str, ttl_seconds: int = 600) -> str | None:
        now = datetime.now(timezone.utc)
        key = f"{job_name}:{now.isoformat()}:{os.getpid()}"
        owner = worker_id()
        expires_at = now + timedelta(seconds=ttl_seconds)
        takeover = await self.session.execute(
            update(SpotJobLock)
            .where(SpotJobLock.job_name == job_name, SpotJobLock.expires_at <= now)
            .values(lock_key=key, worker_id=owner, acquired_at=now, expires_at=expires_at)
            .execution_options(synchronize_session=False)
        )
        if takeover.rowcount:
            await self.session.flush()
            return key

        existing_key = await self.session.scalar(select(SpotJobLock.lock_key).where(SpotJobLock.job_name == job_name))
        if existing_key is not None:
            return None

        self.session.add(SpotJobLock(job_name=job_name, lock_key=key, worker_id=owner, expires_at=expires_at))
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            return None
        return key

    async def release_lock(self, job_name: str, lock_key: str) -> None:
        row = await self.session.get(SpotJobLock, job_name)
        if row and row.lock_key == lock_key:
            await self.session.delete(row)

    async def start_execution(self, job_name: str, scheduled_for: datetime) -> SpotJobExecution:
        row = await self.session.scalar(
            select(SpotJobExecution).where(
                SpotJobExecution.job_name == job_name,
                SpotJobExecution.scheduled_for == scheduled_for,
            )
        )
        now = datetime.now(timezone.utc)
        if row is None:
            row = SpotJobExecution(
                job_name=job_name,
                scheduled_for=scheduled_for,
                status="RUNNING",
                attempt=1,
                started_at=now,
                worker_id=worker_id(),
                build_version=build_version(),
                records_processed=0,
                result_json={},
            )
        else:
            row.status = "RUNNING"
            row.attempt += 1
            row.started_at = now
            row.completed_at = None
            row.worker_id = worker_id()
            row.build_version = build_version()
        self.session.add(row)
        await self.session.flush()
        return row

    async def complete_execution(self, row: SpotJobExecution, result: dict[str, Any], records_processed: int = 0) -> None:
        row.status = "SUCCEEDED"
        row.completed_at = datetime.now(timezone.utc)
        row.records_processed = records_processed
        row.result_json = result
        self.session.add(row)

    async def fail_execution(self, row: SpotJobExecution, exc: Exception) -> None:
        row.status = "FAILED"
        row.completed_at = datetime.now(timezone.utc)
        row.error_code = type(exc).__name__
        row.error_message = str(exc)[:2000]
        self.session.add(row)

    async def latest_success(self, job_name: str) -> SpotJobExecution | None:
        return await self.session.scalar(
            select(SpotJobExecution)
            .where(SpotJobExecution.job_name == job_name, SpotJobExecution.status == "SUCCEEDED")
            .order_by(desc(SpotJobExecution.completed_at))
            .limit(1)
        )


async def guarded_job(
    session: AsyncSession,
    job_name: str,
    work: Callable[[], Awaitable[dict[str, Any]]],
    *,
    window_minutes: int = 5,
    lock_ttl_seconds: int = 600,
) -> dict[str, Any]:
    service = JobStateService(session)
    lock_key = await service.acquire_lock(job_name, ttl_seconds=lock_ttl_seconds)
    if lock_key is None:
        return {"job": job_name, "status": "SKIPPED_LOCKED"}
    execution = await service.start_execution(job_name, utc_window(window_minutes))
    try:
        result = await work()
        records = int(result.get("tokens", result.get("tokens_evaluated", result.get("core", 0))) or 0)
        await service.complete_execution(execution, result, records_processed=records)
        await service.release_lock(job_name, lock_key)
        await session.commit()
        return {"job": job_name, "status": "SUCCEEDED", "result": result}
    except Exception as exc:
        await service.fail_execution(execution, exc)
        await service.release_lock(job_name, lock_key)
        await session.commit()
        raise
