from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.database.session import engine
from app.jobs.scheduler import build_scheduler

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = build_scheduler(settings)
    app.state.scheduler = scheduler
    if settings.scheduler_enabled:
        scheduler.start()
        logger.info("scheduler_started", jobs=[job.id for job in scheduler.get_jobs()])
        logger.info(
            "repository_reset_runtime",
            discontinued_engine="removed",
            trading_workflows="inactive",
            market_scanners="inactive",
            ready_for="Spot Momentum Engine development",
        )
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="2.0.0-reset", lifespan=lifespan)
app.include_router(router)
