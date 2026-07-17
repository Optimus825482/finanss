from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Report
from app.models.core import Notification
from app.schemas import ReportOut, ReportListItem, PipelineStatusOut
from app.orchestrator import orchestrator

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/status", response_model=PipelineStatusOut)
def get_status():
    return orchestrator.status_snapshot()


@router.post("/generate")
async def generate_report(background_tasks: BackgroundTasks, exchange: str | None = None):
    if orchestrator.is_running:
        raise HTTPException(status_code=409, detail="Pipeline zaten calisiyor")

    exchanges = [exchange.upper()] if exchange else None
    label = exchange.upper() if exchange else "TÜM EVREN"
    async def _task():
        await orchestrator.run_pipeline(exchanges)

    background_tasks.add_task(_task)
    return {"started": True, "exchange": label}


@router.post("/generate/deep")
async def generate_deep_report(background_tasks: BackgroundTasks, exchange: str | None = None):
    """Deep Batch: Stage 2 sonrası Fair Value + Prediction + LLM per pick."""
    if orchestrator.is_running:
        raise HTTPException(status_code=409, detail="Pipeline zaten calisiyor")

    exchanges = [exchange.upper()] if exchange else None
    label = exchange.upper() if exchange else "TÜM EVREN"
    async def _task():
        await orchestrator.run_deep_pipeline(exchanges)

    background_tasks.add_task(_task)
    return {"started": True, "exchange": label, "mode": "deep"}


@router.get("/reports/latest", response_model=ReportOut)
def get_latest_report(exchange: str | None = None, db: Session = Depends(get_db)):
    report = (
        db.query(Report)
        .options(joinedload(Report.picks))
        .order_by(Report.created_at.desc())
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Henuz rapor uretilmedi")
    # Exchange filter: sadece ilgili borsanın pick'lerini göster
    if exchange and report.picks:
        is_bist = exchange == "BIST"
        report.picks = [p for p in report.picks if p.ticker.endswith(".IS") == is_bist]
    if not report.picks and exchange:
        raise HTTPException(status_code=404, detail=f"{exchange} icin henuz rapor uretilmedi")
    return report


@router.get("/reports/history", response_model=list[ReportListItem])
def get_report_history(limit: int = 30, exchange: str | None = None, db: Session = Depends(get_db)):
    reports = (
        db.query(Report)
        .options(joinedload(Report.picks))
        .order_by(Report.created_at.desc())
        .all()  # load all for filtering
    )
    items = []
    is_bist = exchange == "BIST" if exchange else None
    for r in reports:
        if len(items) >= limit:
            break
        # Exchange filter: sadece ilgili borsanın pick'lerini içeren raporları göster
        if exchange and r.picks:
            has_match = any(p.ticker.endswith(".IS") if is_bist else not p.ticker.endswith(".IS") for p in r.picks)
            if not has_match:
                continue
        top_ticker = r.picks[0].ticker if r.picks else None
        items.append(ReportListItem(
            id=r.id,
            created_at=r.created_at,
            candidates_scanned=r.candidates_scanned,
            top_ticker=top_ticker,
        ))
    return items


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = (
        db.query(Report)
        .options(joinedload(Report.picks))
        .filter(Report.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Rapor bulunamadi")
    return report


@router.delete("/reports/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Rapor bulunamadi")
    # Iliskili kayitlari sil: predictions, research_memories, notifications, stock_picks
    from app.models.memory import ResearchMemory
    db.query(ResearchMemory).filter(ResearchMemory.source_report_id == report_id).update({ResearchMemory.source_report_id: None})
    db.query(Notification).filter(Notification.report_id == report_id).delete()
    db.delete(report)
    db.commit()
    return {"deleted": True}
