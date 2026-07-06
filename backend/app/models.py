from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    summary = Column(Text)  # genel piyasa yorumu (Türkçe, jargonsuz)
    candidates_scanned = Column(Integer, default=0)

    picks = relationship("StockPick", back_populates="report", cascade="all, delete-orphan")


class StockPick(Base):
    __tablename__ = "stock_picks"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"))

    ticker = Column(String, index=True)
    price = Column(Float)
    momentum_pct = Column(Float)

    fundamental_score = Column(Float)
    sentiment_score = Column(Float)
    risk_score = Column(Float)
    composite_score = Column(Float)

    pe_ratio = Column(Float, nullable=True)
    volatility_annualized = Column(Float, nullable=True)
    max_drawdown_pct = Column(Float, nullable=True)

    narrative = Column(Text)  # bu hisse için kısa Türkçe gerekçe

    report = relationship("Report", back_populates="picks")


class WatchlistItem(Base):
    """Erkan'ın manuel olarak eklediği kişisel izleme listesi (araştırma
    taramasından bağımsız — sadece canlı fiyat takibi için)."""
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True)
    notes = Column(String, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)


class PortfolioPosition(Base):
    """Sanal (paper trading) portföy pozisyonu."""
    __tablename__ = "portfolio_positions"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    quantity = Column(Float)
    entry_price = Column(Float)
    entry_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(String, nullable=True)

    status = Column(String, default="open")  # open | closed
    exit_price = Column(Float, nullable=True)
    exit_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
