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


@router.get("/pending")
def get_pending_orders(
    portfolio_slug: str = Query("bist"),
    db: Session = Depends(get_db),
):
    """Bekleyen emirler — piyasa kapaliyken verilen, acilinca gerceklesecek."""
    portfolio_id = _resolve_portfolio_id(db, portfolio_slug)
    from app.models.core import PendingOrder
    orders = (
        db.query(PendingOrder)
        .filter(PendingOrder.portfolio_id == portfolio_id)
        .filter(PendingOrder.status == "pending")
        .order_by(PendingOrder.created_at.desc())
        .all()
    )
    return [
        {
            "id": o.id, "ticker": o.ticker, "action": o.action,
            "quantity": o.quantity, "price": o.price,
            "reasoning": o.reasoning, "confidence": o.confidence,
            "exchange": o.exchange, "created_at": o.created_at.isoformat() if o.created_at else None,
            "analysis": o.analysis_json,
        }
        for o in orders
    ]


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

    from app.services.agent_logs import start_run, end_run, log_step

    run_id = start_run(portfolio_slug)

    async def _run():
        try:
            log_step(run_id, "market", "Piyasa verileri toplanıyor...")
            result = await asyncio.to_thread(agent.run, exchanges)
            actions = result.get("actions", []) if isinstance(result, dict) else []
            decisions = result.get("decisions", []) if isinstance(result, dict) else []
            log_step(run_id, "result", f"{len(actions)} işlem, {len(decisions)} karar")
            if actions:
                for a in actions[:5]:
                    detail = a.get("action", "?") + " " + a.get("ticker", "?")
                    if a.get("quantity"):
                        detail += f" x{a['quantity']}"
                    log_step(run_id, "trade", detail)
            log_step(run_id, "done", "İşlem tamamlandı")
            end_run(run_id)
        except Exception as e:
            log_step(run_id, "error", str(e))
            end_run(run_id, str(e))

    background_tasks.add_task(_run)
    return {"started": True, "portfolio_slug": portfolio_slug, "mode": "autonomous", "run_id": run_id}


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


@router.get("/logs/{run_id}")
def get_run_logs(run_id: str):
    """Ajan çalışma loglarını döndür — frontend polling için."""
    from app.services.agent_logs import get_run_logs as _get_logs
    return _get_logs(run_id)


@router.get("/active-runs")
def get_active_runs(portfolio_slug: Optional[str] = Query(default=None)):
    """Aktif çalışan ajan run'larını listele."""
    from app.services.agent_logs import get_active_runs as _get_active
    return {"runs": _get_active(portfolio_slug)}
