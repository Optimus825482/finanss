from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.database import SessionLocal  # TODO: use Depends(get_db)
from app.models import PortfolioPosition
from app.schemas import PortfolioPositionIn, PortfolioCloseIn, PortfolioPositionOut, PortfolioSummaryOut
from app.services.market_data import get_live_prices
from app.services.balance_service import (
    get_balance, deposit, record_position_opened, record_position_closed,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


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


@router.get("", response_model=PortfolioSummaryOut)
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

        balance = get_balance(db)

        return PortfolioSummaryOut(
            positions=out_positions,
            total_cost_basis=round(total_cost_basis, 2),
            total_market_value=round(total_market_value, 2),
            total_pl=total_pl,
            total_pl_pct=total_pl_pct,
            cash_balance=balance.cash,
        )
    finally:
        db.close()


@router.post("", response_model=PortfolioPositionOut)
def add_portfolio_position(pos: PortfolioPositionIn):
    db = SessionLocal()
    try:
        ticker = pos.ticker.upper().strip()
        cost = round(pos.quantity * pos.entry_price, 2)

        balance = get_balance(db)
        if balance.cash < cost:
            raise HTTPException(
                status_code=400,
                detail=f"Yetersiz bakiye. Maliyet: ${cost:,.2f}, Mevcut: ${balance.cash:,.2f}",
            )

        p = PortfolioPosition(
            ticker=ticker, quantity=pos.quantity, entry_price=pos.entry_price,
            entry_date=pos.entry_date or datetime.utcnow(), notes=pos.notes, status="open",
        )
        db.add(p)
        db.flush()

        record_position_opened(db, p.id, cost, ticker)

        db.commit()
        db.refresh(p)

        price_map = get_live_prices([ticker])
        return _enrich_position(p, price_map)
    finally:
        db.close()


@router.put("/{position_id}/close", response_model=PortfolioPositionOut)
def close_portfolio_position(position_id: int, body: PortfolioCloseIn):
    db = SessionLocal()
    try:
        p = db.query(PortfolioPosition).filter(PortfolioPosition.id == position_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="Pozisyon bulunamadi")

        proceeds = round(p.quantity * body.exit_price, 2)

        p.status = "closed"
        p.exit_price = body.exit_price
        p.exit_date = body.exit_date or datetime.utcnow()

        record_position_closed(db, p.id, proceeds, p.ticker)

        db.commit()
        db.refresh(p)
        return _enrich_position(p, {})
    finally:
        db.close()


@router.delete("/{position_id}")
def delete_portfolio_position(position_id: int):
    db = SessionLocal()
    try:
        p = db.query(PortfolioPosition).filter(PortfolioPosition.id == position_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="Bulunamadi")

        if p.status == "open":
            refund = round(p.quantity * p.entry_price, 2)
            deposit(db, refund, f"{p.ticker} pozisyon iptal iadesi")

        db.delete(p)
        db.commit()
        return {"deleted": True}
    finally:
        db.close()
