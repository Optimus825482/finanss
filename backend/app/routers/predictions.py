import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db
from app.services.prediction_engine import (
    create_prediction, evaluate_due_predictions, get_predictions,
)

router = APIRouter(prefix="/api/predictions", tags=["predictions"])
logger = logging.getLogger("prediction_engine")


@router.post("/{ticker}")
async def create_forecast(ticker: str, report_id: int | None = None, db: Session = Depends(get_db)):
    """Öngörü oluştur: feature engineering + 7/15/30 gün fiyat tahmini."""
    import yfinance as yf
    from app.services.technicals import compute_all_technicals

    ticker_str = ticker.strip().upper()
    try:
        t = yf.Ticker(ticker_str)
        hist = await asyncio.to_thread(t.history, period="1y", interval="1d")
        hist.index = hist.index.tz_localize(None)

        if hist.empty or len(hist) < 20:
            raise HTTPException(status_code=404, detail="Yetersiz fiyat verisi (en az 20 gun gerekli)")

        closes = hist["Close"].tolist()
        volumes = hist["Volume"].tolist()

        price_history = [
            {"date": str(idx.date()), "close": float(row["Close"]),
             "open": float(row["Open"]), "high": float(row["High"]), "low": float(row["Low"])}
            for idx, row in hist.iterrows()
        ]

        technicals = compute_all_technicals(closes, volumes)

        # Agent skorlarini son rapordan cek (varsa)
        from app.models.core import Report, StockPick
        latest_report = (
            db.query(Report).filter(Report.picks.any(StockPick.ticker == ticker_str))
            .order_by(Report.created_at.desc()).first()
        )
        agent_scores = {}
        if latest_report and latest_report.picks:
            pick = [p for p in latest_report.picks if p.ticker == ticker_str]
            if pick:
                p = pick[0]
                agent_scores = {
                    "fundamental_score": p.fundamental_score,
                    "sentiment_score": p.sentiment_score,
                    "risk_score": p.risk_score,
                    "composite_score": p.composite_score,
                    "momentum_pct": p.momentum_pct,
                    "pe_ratio": p.pe_ratio,
                }
        if not agent_scores:
            agent_scores = {"fundamental_score": 50, "sentiment_score": 50, "risk_score": 50}

        result = await create_prediction(
            db=db, ticker=ticker_str,
            price_history=price_history,
            agent_scores=agent_scores,
            report_id=report_id,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Öngörü oluşturulamadı: {str(e)}")


@router.get("")
def list_predictions(ticker: str | None = None, limit: int = 20, db: Session = Depends(get_db)):
    return get_predictions(db, ticker, limit)


@router.post("/evaluate")
async def evaluate_predictions(db: Session = Depends(get_db)):
    """Target date'i gecmis tum tahminleri degerlendir."""
    results = await evaluate_due_predictions(db)
    return {"evaluated": len(results), "results": results}
