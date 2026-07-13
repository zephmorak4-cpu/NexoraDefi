from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.database.session import engine
from app.jobs.scheduler import build_scheduler
from app.spot.api import router as spot_router

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
            "spot_momentum_runtime",
            product="Solana Spot Momentum Engine",
            universe_mode="ESTABLISHED_ASSETS",
            new_token_discovery="DISABLED",
            new_pair_discovery="DISABLED",
            pump_fun_scanning="DISABLED",
            strategy="TREND_ALIGNED_VOLATILITY_EXPANSION",
            trading_mode="PAPER_ONLY",
        )
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="2.0.0-reset", lifespan=lifespan)
app.include_router(router)
app.include_router(spot_router)
