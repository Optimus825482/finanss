from datetime import datetime
from app.config import now_istanbul

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PortfolioPosition
from app.schemas import PortfolioPositionIn, PortfolioCloseIn, PortfolioPositionOut, PortfolioSummaryOut
from app.services.market_data import get_live_prices
from app.services.balance_service import (
    record_position_opened, record_position_closed, ensure_portfolio,
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
def get_portfolio(portfolio_slug: str = Query("bist"), db: Session = Depends(get_db)):
    portfolio = ensure_portfolio(db, portfolio_slug.lower())
    positions = (db.query(PortfolioPosition)
        .filter(PortfolioPosition.portfolio_id == portfolio.id)
        .order_by(PortfolioPosition.created_at.desc()).all())
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
        cash_balance=portfolio.cash,
    )


@router.get("/open/{ticker}", response_model=list[PortfolioPositionOut])
def get_open_positions(ticker: str, portfolio_slug: str = Query("bist"), db: Session = Depends(get_db)):
    """Bir ticker için açık pozisyonlar, canlı fiyat + kâr/zarar ile."""
    ticker = ticker.upper().strip()
    portfolio = ensure_portfolio(db, portfolio_slug.lower())
    positions = (
        db.query(PortfolioPosition)
        .filter(PortfolioPosition.ticker == ticker, PortfolioPosition.status == "open",
                PortfolioPosition.portfolio_id == portfolio.id)
        .all()
    )
    price_map = get_live_prices([ticker])
    return [_enrich_position(p, price_map) for p in positions]


@router.post("", response_model=PortfolioPositionOut)
def add_portfolio_position(pos: PortfolioPositionIn, portfolio_slug: str = Query("bist"), db: Session = Depends(get_db)):
    ticker = pos.ticker.upper().strip()
    cost = round(pos.quantity * pos.entry_price, 2)
    portfolio = ensure_portfolio(db, portfolio_slug.lower())

    if portfolio.cash < cost:
        raise HTTPException(
            status_code=400,
            detail=f"Yetersiz bakiye. Maliyet: ${cost:,.2f}, Mevcut: ${portfolio.cash:,.2f}",
        )

    p = PortfolioPosition(
        ticker=ticker, quantity=pos.quantity, entry_price=pos.entry_price,
        entry_date=pos.entry_date or now_istanbul(), notes=pos.notes, status="open",
        portfolio_id=portfolio.id,
    )
    db.add(p)
    db.flush()

    record_position_opened(db, p.id, cost, ticker, portfolio_id=portfolio.id)

    db.commit()
    db.refresh(p)

    price_map = get_live_prices([ticker])
    return _enrich_position(p, price_map)


@router.put("/{position_id}/close", response_model=PortfolioPositionOut)
def close_portfolio_position(position_id: int, body: PortfolioCloseIn, portfolio_slug: str = Query("bist"), db: Session = Depends(get_db)):
    portfolio = ensure_portfolio(db, portfolio_slug.lower())
    p = (db.query(PortfolioPosition).filter(PortfolioPosition.id == position_id,
        PortfolioPosition.portfolio_id == portfolio.id).first())
    if not p:
        raise HTTPException(status_code=404, detail="Pozisyon bulunamadi")

    proceeds = round(p.quantity * body.exit_price, 2)

    p.status = "closed"
    p.exit_price = body.exit_price
    p.exit_date = body.exit_date or now_istanbul()

    record_position_closed(db, p.id, proceeds, p.ticker, portfolio_id=portfolio.id)

    db.commit()
    db.refresh(p)
    return _enrich_position(p, {})


@router.delete("/{position_id}")
def delete_portfolio_position(position_id: int, portfolio_slug: str = Query("bist"), db: Session = Depends(get_db)):
    portfolio = ensure_portfolio(db, portfolio_slug.lower())
    p = (db.query(PortfolioPosition).filter(PortfolioPosition.id == position_id,
        PortfolioPosition.portfolio_id == portfolio.id).first())
    if not p:
        raise HTTPException(status_code=404, detail="Bulunamadi")

    if p.status == "open":
        refund = round(p.quantity * p.entry_price, 2)
        record_position_closed(db, p.id, refund, p.ticker, portfolio_id=portfolio.id)

    db.delete(p)
    db.commit()
    return {"deleted": True}
