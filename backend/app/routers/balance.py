from fastapi import APIRouter

from app.database import SessionLocal
from app.schemas import BalanceOut, BalanceTxOut, BalanceDepositIn
from app.services.balance_service import get_balance, deposit, get_transaction_history

router = APIRouter(prefix="/api/balance", tags=["balance"])


@router.get("", response_model=BalanceOut)
def api_get_balance():
    db = SessionLocal()
    try:
        return get_balance(db)
    finally:
        db.close()


@router.post("/deposit", response_model=BalanceOut)
def api_deposit(body: BalanceDepositIn):
    db = SessionLocal()
    try:
        return deposit(db, body.amount, body.note or "Para yatirma")
    finally:
        db.close()


@router.get("/transactions", response_model=list[BalanceTxOut])
def api_get_transactions(limit: int = 50):
    db = SessionLocal()
    try:
        return get_transaction_history(db, limit)
    finally:
        db.close()
