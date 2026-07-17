from datetime import datetime
from app.config import now_istanbul

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=now_istanbul, index=True)
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
    created_at = Column(DateTime, default=now_istanbul, index=True)


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
    created_at = Column(DateTime, default=now_istanbul, index=True)
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

    # Stage 1 pre-screen fields (for agent re-hydration)
    rsi_14 = Column(Float, nullable=True)
    volume_ratio = Column(Float, nullable=True)
    momentum_20d = Column(Float, nullable=True)
    technical_score = Column(Float, nullable=True)

    narrative = Column(Text)

    # Fair Value (adil değer) — Faz 1 enrich
    fair_value = Column(Float, nullable=True)
    margin_pct = Column(Float, nullable=True)
    valuation_assessment = Column(String, nullable=True)

    # LLM enrichment per pick — Faz 1 enrich
    llm_reasoning = Column(Text, nullable=True)
    llm_target_price = Column(Float, nullable=True)
    llm_expected_return_pct = Column(Float, nullable=True)

    report = relationship("Report", back_populates="picks")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True)
    notes = Column(String, nullable=True)
    added_at = Column(DateTime, default=now_istanbul)
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
    entry_date = Column(DateTime, default=now_istanbul)
    notes = Column(String, nullable=True)
    # Çoklu portföy: nullable — null = legacy (portföy-bağımsız)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=True, index=True)

    status = Column(String, default="open")  # open | closed
    exit_price = Column(Float, nullable=True)
    exit_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=now_istanbul)

    __table_args__ = (
        Index("ix_portfolio_positions_portfolio_id", "portfolio_id"),
        Index("ix_portfolio_positions_status", "status"),
    )


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
    # Çoklu portföy: nullable — null = legacy
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=now_istanbul, index=True)

    __table_args__ = (
        Index("ix_trading_decisions_portfolio_id", "portfolio_id"),
    )


class PendingOrder(Base):
    """Bekleyen emir — piyasa kapalıyken verilen, açılınca gerçekleştirilecek."""
    __tablename__ = "pending_orders"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), index=True)
    ticker = Column(String, index=True)
    action = Column(String)  # buy | sell
    quantity = Column(Float)
    price = Column(Float, nullable=True)  # limit fiyat (None = piyasa)
    reasoning = Column(Text)
    analysis_json = Column(JSON, default=dict)  # derin analiz sonucu
    confidence = Column(Float, default=0.7)
    status = Column(String, default="pending")  # pending | executed | cancelled | expired
    exchange = Column(String, nullable=True)  # BIST | US
    created_at = Column(DateTime, default=now_istanbul)
    executed_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_pending_orders_status", "status"),
        Index("ix_pending_orders_portfolio", "portfolio_id"),
    )
