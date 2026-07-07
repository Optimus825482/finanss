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
