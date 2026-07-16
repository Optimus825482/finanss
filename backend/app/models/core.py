from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    summary = Column(Text)
    candidates_scanned = Column(Integer, default=0)

    picks = relationship("StockPick", back_populates="report", cascade="all, delete-orphan")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    # type column - shadows built-in type()
    type = Column(String, default="report")  # report | alert | system
    title = Column(String)
    message = Column(Text, nullable=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class Prediction(Base):
    """Fiyat öngörüsü — self-learning RAG pipeline."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)
    forecast_days = Column(Integer, default=30)
    predicted_prices = Column(JSON, default=dict)
    current_price = Column(Float)
    features_used = Column(JSON, default=dict)
    model_name = Column(String, default="ensemble-light")
    confidence = Column(Float, default=0.5)
    target_date = Column(DateTime, nullable=True)
    actual_price = Column(Float, nullable=True)
    error_pct = Column(Float, nullable=True)
    error_analysis = Column(Text, nullable=True)
    lessons_learned = Column(Text, nullable=True)
    evaluated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    evaluated_at = Column(DateTime, nullable=True)


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

    narrative = Column(Text)

    report = relationship("Report", back_populates="picks")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True)
    notes = Column(String, nullable=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    # stock_analysis skill entegrasyonu: alert/stop/signal takibi
    target_price = Column(Float, nullable=True)        # hedef fiyat (sell tetikleyici)
    stop_price = Column(Float, nullable=True)          # stop-loss fiyatı (exit tetikleyici)
    alert_on_signal = Column(Boolean, default=True)    # sinyal değişiminde uyar
    last_signal = Column(String(50), nullable=True)    # son conclusion: buy/sell/hold


class PortfolioPosition(Base):
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


class TradingDecision(Base):
    __tablename__ = "trading_decisions"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    action = Column(String)
    quantity = Column(Float)
    price = Column(Float)
    total_amount = Column(Float)
    reasoning = Column(Text)
    factors = Column(JSON, default=dict)
    confidence = Column(Float)
    portfolio_value_before = Column(Float, nullable=True)
    portfolio_value_after = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
