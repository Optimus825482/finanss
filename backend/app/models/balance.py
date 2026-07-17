from datetime import datetime
from app.config import now_istanbul

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey

from app.database import Base


class VirtualBalance(Base):
    __tablename__ = "virtual_balance"

    id = Column(Integer, primary_key=True, index=True)
    cash = Column(Float, default=100000.0)  # baslangic 100k USD
    updated_at = Column(DateTime, default=now_istanbul, onupdate=now_istanbul)


class BalanceTransaction(Base):
    """Bakiye hareketleri: para yatirma, cekme, portfoye aktarim."""
    __tablename__ = "balance_transactions"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String)  # deposit | withdraw | transfer_in | transfer_out
    amount = Column(Float)
    note = Column(String, nullable=True)
    position_id = Column(Integer, ForeignKey("portfolio_positions.id"), nullable=True)
    # Çoklu portföy: nullable — null = legacy
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=now_istanbul)
