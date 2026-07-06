from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, SessionLocal
from app.models import Report, WatchlistItem, PortfolioPosition
from app.orchestrator import orchestrator
from app.scheduler import start_scheduler
from app.schemas import (
    ReportOut, ReportListItem, PipelineStatusOut,
    WatchlistItemIn, WatchlistItemOut,
    PortfolioPositionIn, PortfolioCloseIn, PortfolioPositionOut, PortfolioSummaryOut,
)
from app.config import WATCHLIST
from app.services.market_data import get_live_prices

app = FastAPI(title="Uluslararası Hisse Araştırma - Agent Team API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    start_scheduler()


@app.get("/api/watchlist")
def get_watchlist():
    return {"tickers": WATCHLIST, "count": len(WATCHLIST)}


@app.get("/api/status", response_model=PipelineStatusOut)
def get_status():
    return orchestrator.status_snapshot()


@app.post("/api/generate")
async def generate_report(background_tasks: BackgroundTasks):
    if orchestrator.is_running:
        raise HTTPException(status_code=409, detail="Pipeline zaten çalışıyor")

    async def _task():
        await orchestrator.run_pipeline()

    background_tasks.add_task(_task)
    return {"started": True}


@app.get("/api/reports/latest", response_model=ReportOut)
def get_latest_report():
    db = SessionLocal()
    try:
        report = db.query(Report).order_by(Report.created_at.desc()).first()
        if not report:
            raise HTTPException(status_code=404, detail="Henüz rapor üretilmedi")
        return report
    finally:
        db.close()


@app.get("/api/reports/history", response_model=list[ReportListItem])
def get_report_history(limit: int = 30):
    db = SessionLocal()
    try:
        reports = (
            db.query(Report)
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


@app.get("/api/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: int):
    db = SessionLocal()
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Rapor bulunamadı")
        return report
    finally:
        db.close()


# --- Kişisel İzleme Listesi ---

@app.get("/api/watchlist/personal", response_model=list[WatchlistItemOut])
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


@app.post("/api/watchlist/personal", response_model=WatchlistItemOut)
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


@app.delete("/api/watchlist/personal/{item_id}")
def delete_personal_watchlist(item_id: int):
    db = SessionLocal()
    try:
        item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Bulunamadı")
        db.delete(item)
        db.commit()
        return {"deleted": True}
    finally:
        db.close()


# --- Sanal Portföy ---

def _enrich_position(pos: PortfolioPosition, price_map: dict) -> PortfolioPositionOut:
    current_price = market_value = unrealized_pl = unrealized_pl_pct = None

    if pos.status == "open":
        current_price = price_map.get(pos.ticker, {}).get("price")
        if current_price is not None:
            market_value = round(current_price * pos.quantity, 2)
            cost_basis = pos.entry_price * pos.quantity
            unrealized_pl = round(market_value - cost_basis, 2)
            unrealized_pl_pct = round((unrealized_pl / cost_basis) * 100, 2) if cost_basis else 0.0

    return PortfolioPositionOut(
        id=pos.id, ticker=pos.ticker, quantity=pos.quantity, entry_price=pos.entry_price,
        entry_date=pos.entry_date, status=pos.status, exit_price=pos.exit_price,
        exit_date=pos.exit_date, notes=pos.notes, current_price=current_price,
        market_value=market_value, unrealized_pl=unrealized_pl, unrealized_pl_pct=unrealized_pl_pct,
    )


@app.get("/api/portfolio", response_model=PortfolioSummaryOut)
def get_portfolio():
    db = SessionLocal()
    try:
        positions = db.query(PortfolioPosition).order_by(PortfolioPosition.created_at.desc()).all()
        open_tickers = [p.ticker for p in positions if p.status == "open"]
        price_map = get_live_prices(open_tickers)
        out_positions = [_enrich_position(p, price_map) for p in positions]

        total_cost_basis = sum(p.entry_price * p.quantity for p in positions if p.status == "open")
        total_market_value = sum(o.market_value for o in out_positions if o.market_value is not None)
        total_pl = round(total_market_value - total_cost_basis, 2)
        total_pl_pct = round((total_pl / total_cost_basis) * 100, 2) if total_cost_basis else 0.0

        return PortfolioSummaryOut(
            positions=out_positions,
            total_cost_basis=round(total_cost_basis, 2),
            total_market_value=round(total_market_value, 2),
            total_pl=total_pl,
            total_pl_pct=total_pl_pct,
        )
    finally:
        db.close()


@app.post("/api/portfolio", response_model=PortfolioPositionOut)
def add_portfolio_position(pos: PortfolioPositionIn):
    db = SessionLocal()
    try:
        ticker = pos.ticker.upper().strip()
        p = PortfolioPosition(
            ticker=ticker, quantity=pos.quantity, entry_price=pos.entry_price,
            entry_date=pos.entry_date or datetime.utcnow(), notes=pos.notes, status="open",
        )
        db.add(p)
        db.commit()
        db.refresh(p)

        price_map = get_live_prices([ticker])
        return _enrich_position(p, price_map)
    finally:
        db.close()


@app.put("/api/portfolio/{position_id}/close", response_model=PortfolioPositionOut)
def close_portfolio_position(position_id: int, body: PortfolioCloseIn):
    db = SessionLocal()
    try:
        p = db.query(PortfolioPosition).filter(PortfolioPosition.id == position_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="Pozisyon bulunamadı")

        p.status = "closed"
        p.exit_price = body.exit_price
        p.exit_date = body.exit_date or datetime.utcnow()
        db.commit()
        db.refresh(p)
        return _enrich_position(p, {})
    finally:
        db.close()


@app.delete("/api/portfolio/{position_id}")
def delete_portfolio_position(position_id: int):
    db = SessionLocal()
    try:
        p = db.query(PortfolioPosition).filter(PortfolioPosition.id == position_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="Bulunamadı")
        db.delete(p)
        db.commit()
        return {"deleted": True}
    finally:
        db.close()
