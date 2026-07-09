import asyncio
import concurrent.futures
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import SCHEDULE_HOUR, SCHEDULE_MINUTE, TIMEZONE
from app.orchestrator import orchestrator

logger = logging.getLogger("scheduler")


def _run_pipeline_sync():
    try:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, orchestrator.run_pipeline())
            return future.result()
    except Exception as e:
        logger.error(f"Zamanlanmış pipeline çalıştırması başarısız: {e}")


def _run_autonomous_agent_sync():
    """Otonom ajan periyodik calismasi."""
    try:
        from app.services.autonomous_agent import AutonomousAgent
        agent = AutonomousAgent()
        result = agent.run(["NASDAQ", "NYSE"])
        logger.info("Otonom ajan kararlari: %d islem, %d karar",
                     len(result.get("actions", [])), len(result.get("decisions", [])))
    except Exception as e:
        logger.error("Otonom ajan calismasi basarisiz: %s", e)


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone=TIMEZONE)

    # Günlük pipeline (rapor üretimi)
    scheduler.add_job(
        _run_pipeline_sync,
        trigger=CronTrigger(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE),
        id="daily_report",
        replace_existing=True,
    )

    # Otonom ajan (her 30 dakikada bir)
    scheduler.add_job(
        _run_autonomous_agent_sync,
        trigger=IntervalTrigger(minutes=30),
        id="autonomous_agent",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler baslatildi: gunluk rapor (%02d:%02d) + otonom ajan (30dk)",
                 SCHEDULE_HOUR, SCHEDULE_MINUTE)
    return scheduler
