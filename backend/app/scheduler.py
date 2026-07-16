import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import SCHEDULE_HOUR, SCHEDULE_MINUTE, TIMEZONE
from app.orchestrator import orchestrator

logger = logging.getLogger("scheduler")


def _run_pipeline_sync():
    """BackgroundScheduler thread'inden async pipeline'i calistir."""
    try:
        asyncio.run(orchestrator.run_pipeline())
    except Exception as e:
        logger.error(f"Zamanlanmis pipeline calistirmasi basarisiz: {e}")


def _run_autonomous_bist_sync():
    """BIST portföyü için otonom ajan periyodik çalışması."""
    try:
        from app.services.autonomous_agent import AutonomousAgent
        agent = AutonomousAgent(portfolio_slug="bist")
        result = agent.run()  # exchanges config'den (["BIST"])
        logger.info("BIST ajan: %d islem, %d karar",
                     len(result.get("actions", [])), len(result.get("decisions", [])))
    except Exception as e:
        logger.error(f"BIST otonom ajan calismasi basarisiz: {e}")


def _run_autonomous_us_sync():
    """US portföyü (NASDAQ+DJIA) için otonom ajan periyodik çalışması."""
    try:
        from app.services.autonomous_agent import AutonomousAgent
        agent = AutonomousAgent(portfolio_slug="us")
        result = agent.run()  # exchanges config'den (["NASDAQ","DOWJONES"])
        logger.info("US ajan: %d islem, %d karar",
                     len(result.get("actions", [])), len(result.get("decisions", [])))
    except Exception as e:
        logger.error(f"US otonom ajan calismasi basarisiz: {e}")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=TIMEZONE)

    # Günlük pipeline (rapor üretimi)
    scheduler.add_job(
        _run_pipeline_sync,
        trigger=CronTrigger(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE),
        id="daily_report",
        replace_existing=True,
    )

    # Otonom ajan — 2 paralel job (BIST + US)
    scheduler.add_job(
        _run_autonomous_bist_sync,
        trigger=IntervalTrigger(minutes=30),
        id="autonomous_bist",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_autonomous_us_sync,
        trigger=IntervalTrigger(minutes=30),
        id="autonomous_us",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler baslatildi: gunluk rapor (%02d:%02d) + BIST ajan (30dk) + US ajan (30dk)",
                 SCHEDULE_HOUR, SCHEDULE_MINUTE)
    return scheduler
