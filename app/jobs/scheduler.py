from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import Settings


def build_scheduler(settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    return scheduler
