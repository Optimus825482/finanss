from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WatchlistItem
from app.schemas import WatchlistItemIn, WatchlistItemOut, WatchlistAlertOut
from app.services.market_data import get_live_prices
from app.services.screener_service import get_universe

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
def get_watchlist():
    tickers = get_universe()
    return {"tickers": tickers, "count": len(tickers)}


@router.get("/personal", response_model=list[WatchlistItemOut])
def list_personal_watchlist(db: Session = Depends(get_db)):
    items = db.query(WatchlistItem).order_by(WatchlistItem.added_at.desc()).all()
    prices = get_live_prices([i.ticker for i in items])
    return [
        WatchlistItemOut(
            id=i.id, ticker=i.ticker, notes=i.notes, added_at=i.added_at,
            price=prices.get(i.ticker, {}).get("price"),
            change_pct=prices.get(i.ticker, {}).get("change_pct"),
            target_price=i.target_price,
            stop_price=i.stop_price,
            alert_on_signal=i.alert_on_signal,
            last_signal=i.last_signal,
        )
        for i in items
    ]


@router.post("/personal", response_model=WatchlistItemOut)
def add_personal_watchlist(item: WatchlistItemIn, db: Session = Depends(get_db)):
    ticker = item.ticker.upper().strip()
    if db.query(WatchlistItem).filter(WatchlistItem.ticker == ticker).first():
        raise HTTPException(status_code=409, detail="Bu sembol zaten izleme listesinde")

    wi = WatchlistItem(
        ticker=ticker,
        notes=item.notes,
        target_price=item.target_price,
        stop_price=item.stop_price,
        alert_on_signal=item.alert_on_signal if item.alert_on_signal is not None else True,
    )
    db.add(wi)
    db.commit()
    db.refresh(wi)

    p = get_live_prices([ticker]).get(ticker, {})
    return WatchlistItemOut(
        id=wi.id, ticker=wi.ticker, notes=wi.notes, added_at=wi.added_at,
        price=p.get("price"), change_pct=p.get("change_pct"),
        target_price=wi.target_price, stop_price=wi.stop_price,
        alert_on_signal=wi.alert_on_signal, last_signal=wi.last_signal,
    )


@router.delete("/personal/{item_id}")
def delete_personal_watchlist(item_id: int, db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Bulunamadi")
    db.delete(item)
    db.commit()
    return {"deleted": True}


@router.get("/personal/check", response_model=list[WatchlistAlertOut])
def check_alerts(db: Session = Depends(get_db)):
    """İzleme listesindeki alert'leri kontrol et — hedef fiyat, stop-loss, sinyal değişimi."""
    items = db.query(WatchlistItem).all()
    tickers = [i.ticker for i in items]
    prices = get_live_prices(tickers) if tickers else {}

    alerts: list[WatchlistAlertOut] = []
    for item in items:
        price_data = prices.get(item.ticker, {})
        current = price_data.get("price")

        # Hedef fiyat alert
        if item.target_price is not None and current is not None and current >= item.target_price:
            alerts.append(WatchlistAlertOut(
                ticker=item.ticker, alert_type="target",
                current_price=current, threshold=item.target_price,
                last_signal=item.last_signal, triggered=True,
            ))

        # Stop-loss alert
        if item.stop_price is not None and current is not None and current <= item.stop_price:
            alerts.append(WatchlistAlertOut(
                ticker=item.ticker, alert_type="stop",
                current_price=current, threshold=item.stop_price,
                last_signal=item.last_signal, triggered=True,
            ))

    return alerts
