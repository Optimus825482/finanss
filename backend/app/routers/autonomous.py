from fastapi import APIRouter, HTTPException, BackgroundTasks, Query

from app.database import SessionLocal  # TODO: use Depends(get_db)
from app.services.autonomous_agent import AutonomousAgent, get_trading_logs

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])
agent = AutonomousAgent()


@router.get("/portfolio")
def get_agent_portfolio():
    """Ajanin mevcut portfoy ve bakiye durumu."""
    db = SessionLocal()
    try:
        return agent.get_portfolio(db)
    finally:
        db.close()


@router.get("/decisions")
def get_decisions(ticker: str | None = None, limit: int = 50):
    """Ajanin tum karar loglari."""
    db = SessionLocal()
    try:
        return get_trading_logs(db, ticker, limit)
    finally:
        db.close()


@router.post("/run")
async def run_agent(background_tasks: BackgroundTasks, exchanges: list[str] | None = Query(None)):
    """Ajani manuel calistir (veya scheduler'dan tetikle)."""
    async def _run():
        agent.run(exchanges)

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
