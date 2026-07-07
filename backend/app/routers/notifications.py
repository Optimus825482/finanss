from fastapi import APIRouter, Query

from app.database import SessionLocal
from app.models.core import Notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def list_notifications(limit: int = 20):
    db = SessionLocal()
    try:
        items = db.query(Notification).order_by(Notification.created_at.desc()).limit(limit).all()
        return [
            {
                "id": n.id, "type": n.type, "title": n.title,
                "message": n.message, "report_id": n.report_id,
                "is_read": n.is_read, "created_at": n.created_at.isoformat(),
            }
            for n in items
        ]
    finally:
        db.close()


@router.get("/unread-count")
def unread_count():
    db = SessionLocal()
    try:
        count = db.query(Notification).filter(Notification.is_read == False).count()
        return {"count": count}
    finally:
        db.close()


@router.post("/{notif_id}/read")
def mark_read(notif_id: int):
    db = SessionLocal()
    try:
        n = db.query(Notification).filter(Notification.id == notif_id).first()
        if n:
            n.is_read = True
            db.commit()
        return {"ok": True}
    finally:
        db.close()


@router.post("/read-all")
def mark_all_read():
    db = SessionLocal()
    try:
        db.query(Notification).filter(Notification.is_read == False).update({"is_read": True})
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@router.post("/read-by-report/{report_id}")
def mark_read_by_report(report_id: int):
    db = SessionLocal()
    try:
        db.query(Notification).filter(
            Notification.report_id == report_id,
            Notification.is_read == False,
        ).update({"is_read": True})
        db.commit()
        return {"ok": True}
    finally:
        db.close()
