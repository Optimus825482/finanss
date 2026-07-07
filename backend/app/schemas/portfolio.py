from datetime import datetime
from typing import Optional

from pydantic import BaseModel


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
    cash_balance: Optional[float] = None
