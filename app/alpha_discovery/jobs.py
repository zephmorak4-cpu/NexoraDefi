from app.alpha_discovery.engine import SolanaAlphaDiscoveryEngine
from app.alpha_discovery.report import AlphaDiscoveryReportExporter, build_alpha_report_message, build_watchlist_digest
from app.alpha_discovery.services import TelegramAlphaService
from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import SessionFactory
from app.models import AlphaWatchlistToken
from pathlib import Path
from sqlalchemy import desc, select

logger = get_logger(__name__)


async def scan_new_launches() -> dict[str, object]:
    settings = get_settings()
    async with SessionFactory() as session:
        engine = SolanaAlphaDiscoveryEngine(session, settings)
        try:
            counts = await engine.scan()
            return {
                **counts,
                "launch_detector": engine.market_data.last_launch_diagnostics,
                "provider_health": engine.market_data.health.snapshot(),
            }
        except Exception:
            await session.rollback()
            logger.exception("alpha_discovery_scan_failed")
            raise
        finally:
            await engine.close()


async def send_alpha_discovery_report() -> dict[str, object]:
    settings = get_settings()
    output_dir = Path("/tmp/nexora-reports")
    telegram = TelegramAlphaService(settings)
    async with SessionFactory() as session:
        export = await AlphaDiscoveryReportExporter().export(session, output_dir, settings.alpha_report_token_limit)
    try:
        await telegram.send(build_alpha_report_message(export))
        await telegram.send_document(export["docx_path"], "Solana Alpha Discovery Word report. Full token-by-token profiles for manual review.")
        await telegram.send_document(export["pdf_path"], "Solana Alpha Discovery PDF report. Full token-by-token profiles for manual review.")
    finally:
        await telegram.close()
    logger.info("alpha_discovery_report_sent", **export["summary"])
    return export


async def send_alpha_watchlist_digest() -> dict[str, int]:
    settings = get_settings()
    if not settings.send_watchlist_digest and not settings.send_monitor_only_digest:
        logger.info("alpha_watchlist_digest_skipped", reason="digest_disabled")
        return {"watchlist": 0, "sent": 0}
    telegram = TelegramAlphaService(settings)
    decisions = []
    if settings.send_watchlist_digest:
        decisions.append("WATCH_CLOSELY")
    if settings.send_monitor_only_digest:
        decisions.append("MONITOR_ONLY")
    async with SessionFactory() as session:
        watchlist = list(
            (
                await session.scalars(
                    select(AlphaWatchlistToken)
                    .where(AlphaWatchlistToken.decision.in_(decisions))
                    .order_by(desc(AlphaWatchlistToken.final_score), desc(AlphaWatchlistToken.created_at))
                    .limit(settings.max_digest_tokens)
                )
            ).all()
        )
    try:
        sent = await telegram.send(build_watchlist_digest(watchlist))
    finally:
        await telegram.close()
    logger.info("alpha_watchlist_digest_sent", count=len(watchlist), sent=sent)
    return {"watchlist": len(watchlist), "sent": int(sent)}
