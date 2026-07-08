from fastapi import APIRouter, HTTPException, BackgroundTasks
from sqlalchemy.orm import joinedload

from app.database import SessionLocal  # TODO: use Depends(get_db)
from app.models import Report
from app.models.core import Notification
from app.schemas import ReportOut, ReportListItem, PipelineStatusOut
from app.orchestrator import orchestrator

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/status", response_model=PipelineStatusOut)
def get_status():
    return orchestrator.status_snapshot()


@router.post("/generate")
async def generate_report(background_tasks: BackgroundTasks):
    if orchestrator.is_running:
        raise HTTPException(status_code=409, detail="Pipeline zaten calisiyor")

    async def _task():
        await orchestrator.run_pipeline()

    background_tasks.add_task(_task)
    return {"started": True}


@router.get("/reports/latest", response_model=ReportOut)
def get_latest_report():
    db = SessionLocal()
    try:
        report = (
            db.query(Report)
            .options(joinedload(Report.picks))
            .order_by(Report.created_at.desc())
            .first()
        )
        if not report:
            raise HTTPException(status_code=404, detail="Henuz rapor uretilmedi")
        return report
    finally:
        db.close()


@router.get("/reports/history", response_model=list[ReportListItem])
def get_report_history(limit: int = 30):
    db = SessionLocal()
    try:
        reports = (
            db.query(Report)
            .options(joinedload(Report.picks))
            .order_by(Report.created_at.desc())
            .limit(limit)
            .all()
        )
        items = []
        for r in reports:
            top_ticker = r.picks[0].ticker if r.picks else None
            items.append(ReportListItem(
                id=r.id,
                created_at=r.created_at,
                candidates_scanned=r.candidates_scanned,
                top_ticker=top_ticker,
            ))
        return items
    finally:
        db.close()


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: int):
    db = SessionLocal()
    try:
        report = (
            db.query(Report)
            .options(joinedload(Report.picks))
            .filter(Report.id == report_id)
            .first()
        )
        if not report:
            raise HTTPException(status_code=404, detail="Rapor bulunamadi")
        return report
    finally:
        db.close()


@router.delete("/reports/{report_id}")
def delete_report(report_id: int):
    db = SessionLocal()
    try:
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
    finally:
        db.close()
