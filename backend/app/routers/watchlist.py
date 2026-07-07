from fastapi import APIRouter, HTTPException

from app.config import WATCHLIST
from app.database import SessionLocal
from app.models import WatchlistItem
from app.schemas import WatchlistItemIn, WatchlistItemOut
from app.services.market_data import get_live_prices

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
def get_watchlist():
    return {"tickers": WATCHLIST, "count": len(WATCHLIST)}


@router.get("/personal", response_model=list[WatchlistItemOut])
def list_personal_watchlist():
    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).order_by(WatchlistItem.added_at.desc()).all()
        prices = get_live_prices([i.ticker for i in items])
        return [
            WatchlistItemOut(
                id=i.id, ticker=i.ticker, notes=i.notes, added_at=i.added_at,
                price=prices.get(i.ticker, {}).get("price"),
                change_pct=prices.get(i.ticker, {}).get("change_pct"),
            )
            for i in items
        ]
    finally:
        db.close()


@router.post("/personal", response_model=WatchlistItemOut)
def add_personal_watchlist(item: WatchlistItemIn):
    db = SessionLocal()
    try:
        ticker = item.ticker.upper().strip()
        if db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first():
            raise HTTPException(status_code=409, detail="Bu sembol zaten izleme listesinde")

        wi = WatchlistItem(ticker=ticker, notes=item.notes)
        db.add(wi)
        db.commit()
        db.refresh(wi)

        p = get_live_prices([ticker]).get(ticker, {})
        return WatchlistItemOut(
            id=wi.id, ticker=wi.ticker, notes=wi.notes, added_at=wi.added_at,
            price=p.get("price"), change_pct=p.get("change_pct"),
        )
    finally:
        db.close()


@router.delete("/personal/{item_id}")
def delete_personal_watchlist(item_id: int):
    db = SessionLocal()
    try:
        item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Bulunamadi")
        db.delete(item)
        db.commit()
        return {"deleted": True}
    finally:
        db.close()
