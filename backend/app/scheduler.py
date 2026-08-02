import asyncio
import logging
import threading
from concurrent.futures import Future

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import SCHEDULE_HOUR, SCHEDULE_MINUTE, TIMEZONE
from app.orchestrator import orchestrator

logger = logging.getLogger("scheduler")

_scheduler: BackgroundScheduler | None = None
_loop: asyncio.AbstractEventLoop | None = None
_loop_thread: threading.Thread | None = None

# ── Kalıcı event loop (background thread) ──────────────────────────────
# BackgroundScheduler job'ları thread'lerde çalışır; her job'da asyncio.run()
# yeni loop kurup kapatınca create_task ile başlatılan coroutine'ler
# "Task was destroyed" ile sessizce ölüyordu. Tek kalıcı loop, tüm job
# coroutine'lerini güvenle çalıştırır.

_loop_lock = threading.Lock()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """Kalıcı event loop'u (lifespan) başlat. Thread-safe, idempotent."""
    global _loop, _loop_thread
    with _loop_lock:
        if _loop is not None and not _loop.is_closed():
            return _loop
        _loop = asyncio.new_event_loop()
        _loop_thread = threading.Thread(
            target=_loop.run_forever,
            name="orbis-scheduler-loop",
            daemon=True,
        )
        _loop_thread.start()
        logger.info("Kalici event loop baslatildi (thread=%s)", _loop_thread.name)
        return _loop


def _submit(coro) -> Future:
    """Coroutine'i kalıcı loop'a gönder; thread-safe. Sonucu Future ile döndür."""
    loop = _ensure_loop()
    return asyncio.run_coroutine_threadsafe(coro, loop)


def _run_pipeline_sync():
    """BackgroundScheduler thread'inden async pipeline'i kalici loop'ta calistir."""
    try:
        _submit(orchestrator.run_pipeline()).result()
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
    """Start global scheduler singleton. Safe to call multiple times."""
    global _scheduler
    if _scheduler is not None:
        logger.debug("Scheduler already running, skipping duplicate start")
        return _scheduler

    # Kalıcı event loop'u scheduler ile birlikte başlat (aynı yaşam döngüsü)
    _ensure_loop()

    _scheduler = BackgroundScheduler(timezone=TIMEZONE)

    # Günlük pipeline (rapor üretimi)
    _scheduler.add_job(
        _run_pipeline_sync,
        trigger=CronTrigger(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE),
        id="daily_report",
        replace_existing=True,
    )

    # Otonom ajan — 2 paralel job (BIST + US)
    _scheduler.add_job(
        _run_autonomous_bist_sync,
        trigger=IntervalTrigger(minutes=30),
        id="autonomous_bist",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_autonomous_us_sync,
        trigger=IntervalTrigger(minutes=30),
        id="autonomous_us",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler baslatildi: gunluk rapor (%02d:%02d) + BIST ajan (30dk) + US ajan (30dk)",
                 SCHEDULE_HOUR, SCHEDULE_MINUTE)
    return _scheduler


def stop_scheduler():
    """Stop the global scheduler if running."""
    global _scheduler, _loop, _loop_thread
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler durduruldu")
    # Kalıcı event loop'u durdur (daemon thread; güvenli kapanış)
    with _loop_lock:
        if _loop is not None:
            loop = _loop
            _loop = None
            _loop_thread = None
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                pass
