from fastapi import APIRouter, Depends, Query
from app.config import now_istanbul
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import BalanceOut, BalanceTxOut, BalanceDepositIn
from app.services.balance_service import get_transaction_history, ensure_portfolio

router = APIRouter(prefix="/api/balance", tags=["balance"])


@router.get("", response_model=BalanceOut)
def api_get_balance(portfolio_slug: str = Query("bist"), db: Session = Depends(get_db)):
    portfolio = ensure_portfolio(db, portfolio_slug.lower())
    return {"cash": portfolio.cash, "updated_at": portfolio.updated_at}


@router.post("/deposit", response_model=BalanceOut)
def api_deposit(body: BalanceDepositIn, portfolio_slug: str = Query("bist"), db: Session = Depends(get_db)):
    portfolio = ensure_portfolio(db, portfolio_slug.lower())
    portfolio.cash = round(portfolio.cash + body.amount, 2)
    portfolio.updated_at = now_istanbul()
    from app.models import BalanceTransaction
    db.add(BalanceTransaction(type="deposit", amount=body.amount, note=body.note or "Para yatirma", portfolio_id=portfolio.id))
    db.commit()
    db.refresh(portfolio)
    return portfolio


@router.get("/transactions", response_model=list[BalanceTxOut])
def api_get_transactions(limit: int = 50, portfolio_slug: str = Query("bist"), db: Session = Depends(get_db)):
    portfolio = ensure_portfolio(db, portfolio_slug.lower())
    return get_transaction_history(db, portfolio_id=portfolio.id, limit=limit)
