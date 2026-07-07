"""
Sanal bakiye yönetimi. Portföy işlemleriyle entegre.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import VirtualBalance, BalanceTransaction


def get_balance(db: Session) -> VirtualBalance:
    """Bakiyeyi getir, yoksa varsayılan 100k USD ile oluştur."""
    balance = db.query(VirtualBalance).first()
    if not balance:
        balance = VirtualBalance(cash=100_000.0)
        db.add(balance)
        db.commit()
        db.refresh(balance)
    return balance


def deposit(db: Session, amount: float, note: str = "Para yatırma") -> VirtualBalance:
    """Nakit ekle."""
    balance = get_balance(db)
    balance.cash = round(balance.cash + amount, 2)
    balance.updated_at = datetime.utcnow()

    tx = BalanceTransaction(type="deposit", amount=amount, note=note)
    db.add(tx)
    db.commit()
    db.refresh(balance)
    return balance


def withdraw(db: Session, amount: float, note: str = "Para çekme") -> VirtualBalance:
    """Nakit çek."""
    balance = get_balance(db)
    if balance.cash < amount:
        raise ValueError(f"Yetersiz bakiye. Mevcut: ${balance.cash:,.2f}")
    balance.cash = round(balance.cash - amount, 2)
    balance.updated_at = datetime.utcnow()

    tx = BalanceTransaction(type="withdraw", amount=amount, note=note)
    db.add(tx)
    db.commit()
    db.refresh(balance)
    return balance


def record_position_opened(db: Session, position_id: int, cost: float, ticker: str) -> BalanceTransaction:
    """Pozisyon açıldığında bakiyeden düş."""
    balance = get_balance(db)
    balance.cash = round(balance.cash - cost, 2)
    balance.updated_at = datetime.utcnow()

    tx = BalanceTransaction(
        type="transfer_out",
        amount=cost,
        note=f"{ticker} pozisyon açılışı",
        position_id=position_id,
    )
    db.add(tx)
    db.commit()
    db.refresh(balance)
    return tx


def record_position_closed(db: Session, position_id: int, proceeds: float, ticker: str) -> BalanceTransaction:
    """Pozisyon kapandığında bakiyeye ekle."""
    balance = get_balance(db)
    balance.cash = round(balance.cash + proceeds, 2)
    balance.updated_at = datetime.utcnow()

    tx = BalanceTransaction(
        type="transfer_in",
        amount=proceeds,
        note=f"{ticker} pozisyon kapanışı",
        position_id=position_id,
    )
    db.add(tx)
    db.commit()
    db.refresh(balance)
    return tx


def get_transaction_history(db: Session, limit: int = 50) -> list[BalanceTransaction]:
    return (
        db.query(BalanceTransaction)
        .order_by(BalanceTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
