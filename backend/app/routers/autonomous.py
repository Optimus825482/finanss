import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.autonomous_agent import AutonomousAgent, get_trading_logs

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])
logger = logging.getLogger(__name__)
agent = AutonomousAgent()


@router.get("/portfolio")
def get_agent_portfolio(db: Session = Depends(get_db)):
    """Ajanin mevcut portfoy ve bakiye durumu."""
    return agent.get_portfolio(db)


@router.get("/decisions")
def get_decisions(ticker: str | None = None, limit: int = 50, db: Session = Depends(get_db)):
    """Ajanin tum karar loglari."""
    return get_trading_logs(db, ticker, limit)


@router.post("/run")
async def run_agent(background_tasks: BackgroundTasks, exchanges: list[str] | None = Query(default=None)):
    """Ajani manuel calistir (veya scheduler'dan tetikle)."""
    async def _run():
        # Sync agent.run → to_thread ile event loop'u bloklamadan calistir
        await asyncio.to_thread(agent.run, exchanges)

    background_tasks.add_task(_run)
    return {"started": True, "mode": "autonomous"}


@router.post("/schedule")
def schedule_agent():
    """Ajanin periyodik calismasini baslat (her 30 dakikada bir)."""
    from app.scheduler import start_scheduler
    sched = start_scheduler()
    try:
        sched.add_job(
            agent.run,
            trigger="interval",
            minutes=30,
            id="autonomous_agent",
            replace_existing=True,
            kwargs={"exchanges": ["NASDAQ", "NYSE", "BIST"]},
        )
        return {"scheduled": True, "interval": "30 dakika", "exchanges": ["NASDAQ", "NYSE", "BIST"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Zamanlama basarisiz: {e}")


@router.post("/stop")
def stop_agent():
    """Ajanin periyodik calismasini durdur."""
    from app.scheduler import start_scheduler
    sched = start_scheduler()
    try:
        sched.remove_job("autonomous_agent")
        return {"stopped": True}
    except Exception:
        return {"stopped": False, "message": "Ajan zaten calismiyor"}
