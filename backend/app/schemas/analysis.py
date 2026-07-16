"""Pydantic I/O şemaları — stock_analysis skill'in 5 komutu için.

Tüm şemalar Pydantic v2 + from_attributes=True (mevcut desen). Stricter args
şemaları (router bunları validate eder) `*Args` suffix ile ayrılır.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


# --- Position (analyze_stock opsiyonel argümanı) ---

class Position(BaseModel):
    """Kullanıcının mevcut pozisyonu — P/L analizi için."""
    status: Literal["empty", "holding"]
    cost: Optional[float] = None
    shares: Optional[int] = None


# --- 个股分析 (stock analysis) ---

class StockAnalysisRequest(BaseModel):
    ticker: str
    position: Optional[Position] = None


class StockAnalysisResult(BaseModel):
    ticker: str
    markdown: str
    conclusion: Literal["strong_buy", "buy", "hold", "sell", "strong_sell", "unknown"]
    bias_pct: Optional[float] = Field(
        None, description="乖离率: (price - MA20) / MA20 * 100. >5 → buy engellenir"
    )
    data_missing: list[str] = Field(
        default_factory=list, description="Eksik veri alanları — '暂缺' işaretlenmiş"
    )


# --- 股息分析 (dividend) ---

class DividendAnalysisRequest(BaseModel):
    ticker: str


class DividendResult(BaseModel):
    ticker: str
    safety_score: float = Field(..., ge=0, le=100)
    income_rating: Literal["excellent", "good", "moderate", "poor"]
    payout_status: Literal["safe", "moderate", "high", "unsustainable"]
    payout_ratio: Optional[float] = None
    cagr_5y: Optional[float] = Field(None, description="5 yıllık temettü CAGR %")
    consecutive_growth_years: Optional[int] = None
    dividend_aristocrat: bool = Field(False, description="25+ yıl artış = aristokrat")
    current_yield: Optional[float] = None
    data_missing: list[str] = Field(default_factory=list)


# --- 传闻扫描 (rumor scan) ---

RumorType = Literal["ma", "insider", "analyst", "regulatory", "earnings"]


class RumorSignal(BaseModel):
    signal_type: RumorType
    impact_score: int = Field(..., ge=0, le=10)
    headline: str
    source: Optional[str] = None
    url: Optional[str] = None
    timestamp: Optional[datetime] = None
    summary: Optional[str] = None


class RumorScanRequest(BaseModel):
    query: Optional[str] = Field(None, description="Ticker veya sektör sorgusu")


class RumorScanResult(BaseModel):
    query: Optional[str]
    signals: list[RumorSignal]
    total_impact: int = Field(0, ge=0)


# --- 自选股 (watchlist) — manage_watchlist tool args ---

class WatchlistToolArgs(BaseModel):
    """manage_watchlist tool argümanları — router bunu strict validate eder."""
    action: Literal["add", "remove", "list", "check"]
    ticker: Optional[str] = None
    target_price: Optional[float] = None
    stop_price: Optional[float] = None
    alert_on_signal: Optional[bool] = None
    notes: Optional[str] = None


class WatchlistAlert(BaseModel):
    """check_alerts çıktısı — alert tipi + tetiklenmiş durumu."""
    ticker: str
    alert_type: Literal["target", "stop", "signal_change"]
    current_price: Optional[float] = None
    threshold: Optional[float] = None
    last_signal: Optional[str] = None
    triggered: bool = False


# --- K线 (kline chart) ---

class KlineRequest(BaseModel):
    ticker: str
    period: str = Field("6mo", description="yfinance period: 1mo/3mo/6mo/1y/2y")


class KlineResult(BaseModel):
    ticker: str
    chart_png_base64: Optional[str] = None
    vlm_analysis: Optional[str] = None
    pattern_detected: Optional[str] = None
    used_fallback: bool = Field(
        False, description="VLM yoksa metin teknik analiz kullanıldı"
    )
    error: Optional[str] = None


# --- Config ---

class _FromAttr(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# YARDIMCI: ortak config —— tüm Result şemaları için
for _cls in (
    StockAnalysisResult, DividendResult, RumorSignal, RumorScanResult,
    WatchlistAlert, KlineResult,
):
    _cls.model_config = ConfigDict(from_attributes=True)
