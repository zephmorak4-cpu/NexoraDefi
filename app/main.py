from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.analyst.analyst_api import router as analyst_router
from app.api.routes import router
from app.api.risk import router as risk_router
from app.api.smart_money import router as smart_money_router
from app.api.token_intelligence import router as token_intelligence_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.database.session import engine
from app.discovery.discovery_api import router as discovery_router
from app.intelligence.intelligence_api import router as intelligence_router
from app.jobs.scheduler import build_scheduler
from app.smart_money.wallet_api import router as solana_wallet_router

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
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="1.0.0-mvp", lifespan=lifespan)
app.include_router(router)
app.include_router(smart_money_router)
app.include_router(token_intelligence_router)
app.include_router(risk_router)
app.include_router(analyst_router)
app.include_router(solana_wallet_router)
app.include_router(discovery_router)
app.include_router(intelligence_router)
