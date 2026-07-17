"""
Sanal bakiye yönetimi. Portföy işlemleriyle entegre.

Çoklu portföy desteği: her Portfolio'nun ayrı cash'i. Legacy VirtualBalance
hala çalışır ama yeni kod Portfolio kullanır.
"""
from datetime import datetime
from app.config import now_istanbul
from typing import Optional

from sqlalchemy.orm import Session

from app.models import VirtualBalance, BalanceTransaction, Portfolio


# --- Legacy VirtualBalance (geri uyumluluk) ---

def get_balance(db: Session) -> VirtualBalance:
    """[LEGACY] Bakiyeyi getir, yoksa varsayılan 100k USD ile oluştur.

    Yeni kod: get_portfolio_balance(db, portfolio_id) kullanın.
    """
    balance = db.query(VirtualBalance).first()
    if not balance:
        balance = VirtualBalance(cash=100_000.0)
        db.add(balance)
        db.flush()
        db.refresh(balance)
    return balance


# --- Portfolio-bilinçli fonksiyonlar (yeni) ---

def get_portfolio_by_slug(db: Session, slug: str) -> Optional[Portfolio]:
    """Slug ile Portfolio kaydını getir. Yoksa None."""
    return db.query(Portfolio).filter(Portfolio.slug == slug).first()


def ensure_portfolio(db: Session, slug: str) -> Portfolio:
    """Portfolio kaydını getir, yoksa PORTFOLIOS config'den oluştur.

    Migration seed'i yapmamışsa bile runtime'da guarantee.
    """
    from app.config import PORTFOLIOS

    p = get_portfolio_by_slug(db, slug)
    if p is not None:
        # Mevcut portföyün cash'ini config'deki değerle senkronize et
        # (yeni bakiye ayarları için — pozisyonları etkilemez)
        cfg = PORTFOLIOS.get(slug, {})
        if cfg:
            configured_cash = cfg.get("cash", 10_000.0)
            # Sadece cash config'den düşükse güncelle (manual artışları ezme)
            if p.cash < configured_cash:
                p.cash = configured_cash
                db.flush()
        return p
    # Config'den oluştur
    cfg = PORTFOLIOS.get(slug)
    if cfg is None:
        raise ValueError(f"Bilinmeyen portföy slug: {slug}")
    p = Portfolio(
        slug=slug,
        display_name=cfg["display_name"],
        exchanges=cfg.get("exchanges", []),
        cash=cfg.get("cash", 10_000.0),
        max_positions=cfg.get("max_positions", 8),
        max_per_position_pct=cfg.get("max_per_position_pct", 0.25),
        is_active=True,
    )
    db.add(p)
    db.flush()
    db.refresh(p)
    return p


def get_portfolio_balance(db: Session, portfolio_id: int) -> float:
    """Portfolio.cash getir."""
    p = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if p is None:
        raise ValueError(f"Portföy bulunamadı: id={portfolio_id}")
    return p.cash


def record_position_opened(
    db: Session,
    position_id: int,
    cost: float,
    ticker: str,
    portfolio_id: Optional[int] = None,
) -> BalanceTransaction:
    """Pozisyon açıldığında bakiyeden düş. Caller must commit.

    portfolio_id verilirse Portfolio.cash düşülür (yeni), yoksa legacy VirtualBalance.
    """
    if portfolio_id is not None:
        p = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if p is None:
            raise ValueError(f"Portföy bulunamadı: id={portfolio_id}")
        p.cash = round(p.cash - cost, 2)
        p.updated_at = now_istanbul()
    else:
        # Legacy fallback
        balance = get_balance(db)
        balance.cash = round(balance.cash - cost, 2)
        balance.updated_at = now_istanbul()

    tx = BalanceTransaction(
        type="transfer_out",
        amount=cost,
        note=f"{ticker} pozisyon açılışı",
        position_id=position_id,
        portfolio_id=portfolio_id,
    )
    db.add(tx)
    db.flush()
    return tx


def record_position_closed(
    db: Session,
    position_id: int,
    proceeds: float,
    ticker: str,
    portfolio_id: Optional[int] = None,
) -> BalanceTransaction:
    """Pozisyon kapandığında bakiyeye ekle. Caller must commit."""
    if portfolio_id is not None:
        p = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        if p is None:
            raise ValueError(f"Portföy bulunamadı: id={portfolio_id}")
        p.cash = round(p.cash + proceeds, 2)
        p.updated_at = now_istanbul()
    else:
        balance = get_balance(db)
        balance.cash = round(balance.cash + proceeds, 2)
        balance.updated_at = now_istanbul()

    tx = BalanceTransaction(
        type="transfer_in",
        amount=proceeds,
        note=f"{ticker} pozisyon kapanışı",
        position_id=position_id,
        portfolio_id=portfolio_id,
    )
    db.add(tx)
    db.flush()
    return tx


def get_transaction_history(db: Session, portfolio_id: Optional[int] = None, limit: int = 50) -> list[BalanceTransaction]:
    """Bakiye hareketleri. portfolio_id verilirse sadece o portföyün."""
    q = db.query(BalanceTransaction)
    if portfolio_id is not None:
        q = q.filter(BalanceTransaction.portfolio_id == portfolio_id)
    return q.order_by(BalanceTransaction.created_at.desc()).limit(limit).all()


def reset_balance(db: Session, portfolio_id: int, starting_cash: float = 10_000.0) -> Portfolio:
    """Portfolio.cash sıfırla + o portföyün transactions sil. Caller must commit."""
    p = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if p is None:
        raise ValueError(f"Portföy bulunamadı: id={portfolio_id}")
    # Sadece bu portföyün transactions sil
    db.query(BalanceTransaction).filter(
        BalanceTransaction.portfolio_id == portfolio_id
    ).delete(synchronize_session=False)
    p.cash = round(float(starting_cash), 2)
    p.updated_at = now_istanbul()
    db.flush()
    db.refresh(p)
    return p


# --- Legacy deposit/withdraw (VirtualBalance) — geri uyumluluk ---

def deposit(db: Session, amount: float, note: str = "Para yatırma") -> VirtualBalance:
    """[LEGACY] Nakit ekle. Yeni kod Portfolio.cash direkt güncelle."""
    balance = get_balance(db)
    balance.cash = round(balance.cash + amount, 2)
    balance.updated_at = now_istanbul()
    tx = BalanceTransaction(type="deposit", amount=amount, note=note)
    db.add(tx)
    db.flush()
    db.refresh(balance)
    return balance


def withdraw(db: Session, amount: float, note: str = "Para çekme") -> VirtualBalance:
    """[LEGACY] Nakit çek."""
    balance = get_balance(db)
    if balance.cash < amount:
        raise ValueError(f"Yetersiz bakiye. Mevcut: ${balance.cash:,.2f}")
    balance.cash = round(balance.cash - amount, 2)
    balance.updated_at = now_istanbul()
    tx = BalanceTransaction(type="withdraw", amount=amount, note=note)
    db.add(tx)
    db.flush()
    db.refresh(balance)
    return balance
