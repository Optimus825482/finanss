from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.utils.sanitize import sanitize_float


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

    @field_validator(
        "price", "momentum_pct", "fundamental_score", "sentiment_score",
        "risk_score", "composite_score",
        mode="before",
    )
    @classmethod
    def _nan_to_zero(cls, v):
        """Catch NaN/Inf floats from DB — required fields default to 0.0."""
        return sanitize_float(v, 0.0)

    @field_validator(
        "pe_ratio", "volatility_annualized", "max_drawdown_pct",
        mode="before",
    )
    @classmethod
    def _nan_to_none(cls, v):
        """Catch NaN/Inf floats from DB — optional fields default to None."""
        return sanitize_float(v, None)

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
    mode: Optional[str] = None
    progress: list[str] = []
    last_error: Optional[str] = None
