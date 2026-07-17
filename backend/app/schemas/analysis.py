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
        None, description="bias: (price - MA20) / MA20 * 100. >5 → buy engellenir"
    )
    data_missing: list[str] = Field(
        default_factory=list, description="Eksik veri alanları — 'veri yok' işaretlenmiş"
    )
    # Görsel dashboard için ham veriler
    price_history: list[dict] = Field(
        default_factory=list,
        description="Son 60 gün OHLCV: [{date, open, high, low, close, volume}]",
    )
    scores: dict = Field(
        default_factory=dict,
        description="Skorlar: {fundamental, sentiment, risk, composite}",
    )
    position_pl: Optional[dict] = Field(
        None, description="P/L: {cost_total, current_total, pl, pl_pct}",
    )
    # Küresel makro göstergeler
    macro_indicators: list[dict] = Field(
        default_factory=list,
        description="Küresel makro: [{name, label, price, change_pct, sentiment, unit}]",
    )
    # LLM zenginleştirme
    llm_reasoning: Optional[str] = Field(
        None, description="AI gerekçe açıklaması (2-3 cümle, Türkçe)"
    )
    llm_target_price: Optional[float] = Field(
        None, description="12 aylık hedef fiyat tahmini"
    )
    llm_expected_return_pct: Optional[float] = Field(
        None, description="Beklenen % getiri (12 aylık)"
    )
    momentum_pct: Optional[float] = Field(
        None, description="Son 5 günlük momentum %"
    )
    # Faz 2 zenginlestirme: Fair Value
    fair_value: Optional[float] = Field(
        None, description="Ensemble adil değer (Graham+DCF+Lynch+PE)"
    )
    margin_pct: Optional[float] = Field(
        None, description="Adil değere göre marj % (pozitif = iskontolu)"
    )
    valuation_assessment: Optional[str] = Field(
        None, description="Değerleme: 'Asiri degerli', 'Adil degerde', 'Dusuk degerli'"
    )
    fair_value_models: list[dict] = Field(
        default_factory=list, description="Bireysel model sonuçları [{method, value, inputs}]"
    )
    # Faz 2 zenginlestirme: Prediction
    predictions: Optional[dict] = Field(
        None, description="7/15/30 gün fiyat tahminleri {day_7, day_15, day_30}"
    )


# --- 股息分析 (dividend) ---

class DividendAnalysisRequest(BaseModel):
    ticker: str


class DividendResult(BaseModel):
    ticker: str
    safety_score: float = Field(..., ge=0, le=100)
    income_rating: Literal["excellent", "good", "moderate", "poor"]
    payout_status: Literal["safe", "moderate", "high", "unsustainable", "unknown"]
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


# --- Sector Rotation ---

class SectorRotationRequest(BaseModel):
    query: Optional[str] = Field(None, description="Opsiyonel: belirli bir ticker için sektör")


class SectorData(BaseModel):
    name: str
    ticker_count: int
    avg_return_pct: float
    tickers: list[str] = Field(default_factory=list)


class SectorRotationResult(BaseModel):
    query: Optional[str] = None
    sector: Optional[str] = None
    sectors: list[dict] = Field(default_factory=list)
    top_sector: Optional[str] = None
    bottom_sector: Optional[str] = None


# --- Correlation Matrix ---

class CorrelationRequest(BaseModel):
    tickers: Optional[str] = Field(None, description="Virgülle ayrılmış ticker listesi")


class CorrelationResult(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    matrix: list[list[float]] = Field(default_factory=list)
    clusters: list[list[str]] = Field(default_factory=list)
    highest_correlation: Optional[dict] = None
    lowest_correlation: Optional[dict] = None
    error: Optional[str] = None


# --- Insider Activity ---

class InsiderRequest(BaseModel):
    ticker: str


class InsiderTransaction(BaseModel):
    type: str
    shares: int = 0
    value: Optional[float] = None
    insider_name: str = "Bilinmiyor"
    date: str = ""


class InsiderResult(BaseModel):
    ticker: str
    transactions: list[dict] = Field(default_factory=list)
    net_sentiment: str = "neutral"
    buy_count: int = 0
    sell_count: int = 0
    buy_value: float = 0.0
    sell_value: float = 0.0
    data_missing: list[str] = Field(default_factory=list)


# --- Unusual Options ---

class UnusualOptionsRequest(BaseModel):
    ticker: str


class UnusualOptionsResult(BaseModel):
    ticker: str
    options_activity: list[dict] = Field(default_factory=list)
    put_call_ratio: Optional[float] = None
    unusual_count: int = 0
    sentiment: str = "neutral"
    data_missing: list[str] = Field(default_factory=list)


# --- Earnings Surprise ---

class EarningsSurpriseRequest(BaseModel):
    ticker: str


class EarningsSurpriseResult(BaseModel):
    ticker: str
    history: list[dict] = Field(default_factory=list)
    avg_surprise_pct: float = 0.0
    next_earnings_date: Optional[str] = None
    beat_count: int = 0
    miss_count: int = 0
    sentiment: str = "neutral"
    data_missing: list[str] = Field(default_factory=list)


# --- Seasonality ---

class SeasonalityRequest(BaseModel):
    ticker: str


class SeasonalityResult(BaseModel):
    ticker: str
    monthly_returns: dict = Field(default_factory=dict)
    quarterly_patterns: dict = Field(default_factory=dict)
    best_month: Optional[str] = None
    worst_month: Optional[str] = None
    best_quarter: Optional[str] = None
    worst_quarter: Optional[str] = None
    data_missing: list[str] = Field(default_factory=list)


# --- Fair Value (bağımsız skill) ---

class FairValueSkillRequest(BaseModel):
    ticker: str


class FairValueSkillResult(BaseModel):
    ticker: str
    fair_value: Optional[float] = None
    current_price: Optional[float] = None
    margin_pct: Optional[float] = None
    assessment: Optional[str] = None
    models: list[dict] = Field(default_factory=list)
    markdown: str = ""
    data_missing: list[str] = Field(default_factory=list)


# YARDIMCI: ortak config —— tüm Result şemaları için
for _cls in (
    StockAnalysisResult, DividendResult, RumorSignal, RumorScanResult,
    WatchlistAlert, KlineResult,
    SectorRotationResult, CorrelationResult, InsiderResult,
    UnusualOptionsResult, EarningsSurpriseResult, SeasonalityResult,
    FairValueSkillResult,
):
    _cls.model_config = ConfigDict(from_attributes=True)
