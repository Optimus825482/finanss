import logging

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query

from app.database import SessionLocal
from app.orchestrator import orchestrator
from app.services.screener_service import list_exchanges, get_universe
from app.config import STOCK_UNIVERSE

router = APIRouter(prefix="/api/screen", tags=["screen"])

logger = logging.getLogger(__name__)


@router.get("/exchanges")
def get_exchanges():
    """Kullanilabilir borsa listesini dondur."""
    return list_exchanges()


@router.get("/universe")
def get_ticker_universe(exchange: str | None = Query(default=None)):
    """Secili borsadaki hisseleri dondur."""
    if exchange:
        tickers = get_universe([exchange])
        return {"exchange": exchange, "count": len(tickers), "tickers": tickers}
    return {"exchanges": [{"slug": k, "ticker_count": len(v)} for k, v in STOCK_UNIVERSE.items() if len(v) > 0]}


@router.post("/generate")
async def generate_screened_report(
    background_tasks: BackgroundTasks,
    exchanges: list[str] = Query(default=None),
):
    """Iki asamali pipeline: secili borsalari tara → derin analiz → rapor."""
    if orchestrator.is_running:
        raise HTTPException(status_code=409, detail="Pipeline zaten calisiyor")

    if not exchanges:
        raise HTTPException(status_code=400, detail="En az bir borsa secmelisin")

    async def _task():
        try:
            report_id = await orchestrator.run_pipeline(exchanges=exchanges)

            # Notification (BG task → SessionLocal dogrudan)
            if report_id:
                db = SessionLocal()
                try:
                    from app.models.core import Notification
                    ex_labels = ", ".join(exchanges)
                    db.add(Notification(type="report", title="Tarama Tamamlandi",
                        message=f"{ex_labels} borsalarinda iki asamali tarama tamamlandi.", report_id=report_id))
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.error("Notification persist failed for report #%s: %s", report_id, e)
                finally:
                    db.close()
        except Exception as e:
            logger.error("Screened report generation failed: %s", e)

    background_tasks.add_task(_task)
    return {"started": True, "exchanges": exchanges, "mode": "two-stage"}
