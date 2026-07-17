from datetime import datetime
"""Portfolio modeli — çoklu portföy yönetimi (BIST + US).

Her portföyün ayrı bakiyesi (cash), universe'i (exchanges), risk parametreleri.
VirtualBalance deprecate — yeni kod Portfolio.cash kullanır.
"""
from app.config import now_istanbul

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON

from app.database import Base


class Portfolio(Base):
    """Otonom yönetilen portföy — BIST veya US (NASDAQ+DJIA) gibi."""
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)        # "bist" | "us"
    display_name = Column(String)                          # "BIST Portföyü"
    exchanges = Column(JSON, default=list)                 # ["BIST"] | ["NASDAQ","DOWJONES"]
    cash = Column(Float, default=10000.0)
    max_positions = Column(Integer, default=8)
    max_per_position_pct = Column(Float, default=0.25)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=now_istanbul)
    updated_at = Column(DateTime, default=now_istanbul, onupdate=now_istanbul)
