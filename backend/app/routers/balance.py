from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import BalanceOut, BalanceTxOut, BalanceDepositIn
from app.services.balance_service import get_balance, deposit, get_transaction_history

router = APIRouter(prefix="/api/balance", tags=["balance"])


@router.get("", response_model=BalanceOut)
def api_get_balance(db: Session = Depends(get_db)):
    return get_balance(db)


@router.post("/deposit", response_model=BalanceOut)
def api_deposit(body: BalanceDepositIn, db: Session = Depends(get_db)):
    result = deposit(db, body.amount, body.note or "Para yatirma")
    db.commit()
    return result


@router.get("/transactions", response_model=list[BalanceTxOut])
def api_get_transactions(limit: int = 50, db: Session = Depends(get_db)):
    return get_transaction_history(db, limit)
