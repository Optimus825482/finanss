from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class StockPickOut(BaseModel):
    ticker: str
    price: float
    momentum_pct: float
    fundamental_score: float
    sentiment_score: float
    risk_score: float
    composite_score: float
    pe_ratio: Optional[float] = None
    volatility_annualized: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    narrative: str

    class Config:
        from_attributes = True


class ReportOut(BaseModel):
    id: int
    created_at: datetime
    summary: str
    candidates_scanned: int
    picks: list[StockPickOut]

    class Config:
        from_attributes = True


class ReportListItem(BaseModel):
    id: int
    created_at: datetime
    candidates_scanned: int
    top_ticker: Optional[str] = None

    class Config:
        from_attributes = True


class AgentStatusOut(BaseModel):
    name: str
    label: str
    status: str  # idle | running | done | error
    detail: Optional[str] = None
    updated_at: Optional[datetime] = None


class PipelineStatusOut(BaseModel):
    running: bool
    agents: list[AgentStatusOut]


# --- Kişisel İzleme Listesi ---

class WatchlistItemIn(BaseModel):
    ticker: str
    notes: Optional[str] = None


class WatchlistItemOut(BaseModel):
    id: int
    ticker: str
    notes: Optional[str] = None
    added_at: datetime
    price: Optional[float] = None
    change_pct: Optional[float] = None

    class Config:
        from_attributes = True


# --- Sanal Portföy ---

class PortfolioPositionIn(BaseModel):
    ticker: str
    quantity: float
    entry_price: float
    entry_date: Optional[datetime] = None
    notes: Optional[str] = None


class PortfolioCloseIn(BaseModel):
    exit_price: float
    exit_date: Optional[datetime] = None


class PortfolioPositionOut(BaseModel):
    id: int
    ticker: str
    quantity: float
    entry_price: float
    entry_date: datetime
    status: str
    exit_price: Optional[float] = None
    exit_date: Optional[datetime] = None
    notes: Optional[str] = None
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pl: Optional[float] = None
    unrealized_pl_pct: Optional[float] = None

    class Config:
        from_attributes = True


class PortfolioSummaryOut(BaseModel):
    positions: list[PortfolioPositionOut]
    total_cost_basis: float
    total_market_value: float
    total_pl: float
    total_pl_pct: float
