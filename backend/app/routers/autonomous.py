"""Otonom ajan HTTP uçları — portföy-bilinçli.

Her endpoint `portfolio_slug` query parametresi alır ("bist" | "us").
Her request'te uygun AutonomousAgent instance yaratılır — state modül seviyesinde değil.
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.autonomous_agent import AutonomousAgent, get_trading_logs
from app.services.balance_service import ensure_portfolio

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])
logger = logging.getLogger(__name__)

VALID_SLUGS = ("bist", "us")


def _resolve_portfolio_id(db: Session, slug: str) -> int:
    """Slug → portfolio_id (DB'de guarantee)."""
    if slug not in VALID_SLUGS:
        raise HTTPException(status_code=400, detail=f"Geçersiz portföy: {slug}. Geçerli: {VALID_SLUGS}")
    p = ensure_portfolio(db, slug)
    return p.id


@router.get("/portfolio")
def get_agent_portfolio(
    portfolio_slug: str = Query("bist", description="bist | us"),
    db: Session = Depends(get_db),
):
    """Ajanin mevcut portfoy ve bakiye durumu."""
    _resolve_portfolio_id(db, portfolio_slug)  # validate + ensure
    agent = AutonomousAgent(portfolio_slug=portfolio_slug)
    return agent.get_portfolio(db)


@router.get("/decisions")
def get_decisions(
    portfolio_slug: str = Query("bist"),
    ticker: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Ajanin tum karar loglari — sadece bu portföyün."""
    portfolio_id = _resolve_portfolio_id(db, portfolio_slug)
    return get_trading_logs(db, ticker, limit, portfolio_id=portfolio_id)


@router.post("/run")
async def run_agent(
    background_tasks: BackgroundTasks,
    portfolio_slug: str = Query("bist"),
    exchanges: Optional[list[str]] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Ajani manuel calistir. exchanges None ise config'den (portföyün exchanges'i)."""
    _resolve_portfolio_id(db, portfolio_slug)
    agent = AutonomousAgent(portfolio_slug=portfolio_slug)

    async def _run():
        await asyncio.to_thread(agent.run, exchanges)

    background_tasks.add_task(_run)
    return {"started": True, "portfolio_slug": portfolio_slug, "mode": "autonomous"}


@router.post("/schedule")
def schedule_agent(
    portfolio_slug: str = Query("bist"),
    db: Session = Depends(get_db),
):
    """Ajanin periyodik calismasini baslat (her 30 dakikada bir).

    Scheduler zaten 2 job (autonomous_bist + autonomous_us) ile başlıyor.
    Bu endpoint manuel restart için.
    """
    _resolve_portfolio_id(db, portfolio_slug)
    job_id = f"autonomous_{portfolio_slug}"
    from app.scheduler import start_scheduler
    sched = start_scheduler()
    try:
        # Önce remove (varsa), sonra add
        try:
            sched.remove_job(job_id)
        except Exception:
            pass
        agent = AutonomousAgent(portfolio_slug=portfolio_slug)
        sched.add_job(
            agent.run,
            trigger="interval",
            minutes=30,
            id=job_id,
            replace_existing=True,
        )
        return {"scheduled": True, "portfolio_slug": portfolio_slug, "interval": "30 dakika"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Zamanlama basarisiz: {e}")


@router.post("/stop")
def stop_agent(
    portfolio_slug: str = Query("bist"),
    db: Session = Depends(get_db),
):
    """Ajanin periyodik calismasini durdur."""
    _resolve_portfolio_id(db, portfolio_slug)
    job_id = f"autonomous_{portfolio_slug}"
    from app.scheduler import start_scheduler
    sched = start_scheduler()
    try:
        sched.remove_job(job_id)
        return {"stopped": True, "portfolio_slug": portfolio_slug}
    except Exception:
        return {"stopped": False, "portfolio_slug": portfolio_slug, "message": "Ajan zaten calismiyor"}
