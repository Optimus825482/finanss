import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import SCHEDULE_HOUR, SCHEDULE_MINUTE, TIMEZONE
from app.orchestrator import orchestrator

logger = logging.getLogger("scheduler")


def _run_pipeline_sync():
    try:
        asyncio.run(orchestrator.run_pipeline())
    except Exception as e:
        logger.error(f"Zamanlanmış pipeline çalıştırması başarısız: {e}")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        _run_pipeline_sync,
        trigger=CronTrigger(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE),
        id="daily_report",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
